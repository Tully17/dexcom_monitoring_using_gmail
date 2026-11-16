import logging
import os
import sys
import time
import smtplib

from email.message import EmailMessage
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from pydexcom import Dexcom


# ============================================================
# CONFIGURATION
# ============================================================

DEXCOM_USERNAME = os.getenv("DEXCOM_USERNAME")
DEXCOM_PASSWORD = os.getenv("DEXCOM_PASSWORD")

TRUE_NAME = os.getenv("TRUE_NAME")

DEXCOM_REGION = os.getenv("DEXCOM_REGION", "us")

DEXCOM_REGION = os.getenv("DEXCOM_REGION", "us")

SMTP_SERVER = os.getenv("SMTP_SERVER", "smtp.gmail.com")

SMTP_PORT = int(
    os.getenv("SMTP_PORT", "587")
)

SMTP_USERNAME = os.getenv("SMTP_USERNAME")

SMTP_PASSWORD = os.getenv("SMTP_PASSWORD")

EMAIL_FROM = os.getenv("EMAIL_FROM")

EMAIL_TO = [
    address.strip()
    for address in os.getenv("EMAIL_TO", "").split(",")
    if address.strip()
]

TIMEZONE_NAME = os.getenv(
    "TZ",
    "America/New_York"
)

POLL_INTERVAL_SECONDS = int(
    os.getenv("POLL_INTERVAL_SECONDS", "300")
)

URGENT_LOW_ALERT = int(
    os.getenv("URGENT_LOW_ALERT", "55")
)

LOW_ALERT = int(
    os.getenv("LOW_ALERT", "70")
)

HIGH_ALERT = int(
    os.getenv("HIGH_ALERT", "250")
)

STALE_AFTER_MINUTES = int(
    os.getenv("STALE_AFTER_MINUTES", "20")
)

WORK_START_HOUR = int(
    os.getenv("WORK_START_HOUR", "7")
)

WORK_END_HOUR = int(
    os.getenv("WORK_END_HOUR", "16")
)

# ============================================================
# LOGGING
# ============================================================

LOG_DIRECTORY = "/data/logs"

os.makedirs(LOG_DIRECTORY, exist_ok=True)

LOG_FILE = os.path.join(
    LOG_DIRECTORY,
    "dexcom_monitor.log"
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE),
        logging.StreamHandler(sys.stdout)
    ]
)

logger = logging.getLogger("dexcom-monitor")


# ============================================================
# STATE
# ============================================================

last_dexcom_error_message = None
last_dexcom_error_time = None

last_email_error_time = None

heartbeat_sent_date = None

stale_alert_active = False

low_alert_active = False
urgent_low_alert_active = False
high_alert_active = False

rapid_rise_active = False
rapid_fall_active = False

# ============================================================
# TIMEZONE
# ============================================================

try:
    LOCAL_TZ = ZoneInfo(TIMEZONE_NAME)

except Exception:
    logger.exception(
        "Unable to load timezone '%s'. Falling back to UTC.",
        TIMEZONE_NAME
    )

    LOCAL_TZ = ZoneInfo("UTC")


# ============================================================
# VALIDATION
# ============================================================

def validate_configuration():

    missing = []

    if not DEXCOM_USERNAME:
        missing.append("DEXCOM_USERNAME")

    if not DEXCOM_PASSWORD:
        missing.append("DEXCOM_PASSWORD")

    if not SMTP_SERVER:
        missing.append("SMTP_SERVER")

    if not SMTP_USERNAME:
        missing.append("SMTP_USERNAME")

    if not SMTP_PASSWORD:
        missing.append("SMTP_PASSWORD")

    if not EMAIL_FROM:
        missing.append("EMAIL_FROM")

    if not EMAIL_TO:
        missing.append("EMAIL_TO")

    if missing:

        logger.error(
            "Missing required environment variables: %s",
            ", ".join(missing)
        )

        raise RuntimeError(
            "Missing required configuration: "
            + ", ".join(missing)
        )

# ============================================================
# EMAIL
# ============================================================

def send_email(subject, message):

    global last_email_error_time

    if not EMAIL_TO:

        logger.error(
            "No email recipients configured."
        )

        return False

    try:

        email = EmailMessage()

        email["Subject"] = subject
        email["From"] = EMAIL_FROM
        email["To"] = ", ".join(EMAIL_TO)

        email.set_content(message)

        with smtplib.SMTP(
            SMTP_SERVER,
            SMTP_PORT,
            timeout=20
        ) as smtp:

            smtp.ehlo()

            smtp.starttls()

            smtp.ehlo()

            smtp.login(
                SMTP_USERNAME,
                SMTP_PASSWORD
            )

            smtp.send_message(email)

        logger.info(
            "Email sent successfully: %s",
            subject
        )

        return True

    except Exception as error:

        now = datetime.now(LOCAL_TZ)

        if (
            last_email_error_time is None
            or now - last_email_error_time
            > timedelta(minutes=10)
        ):

            logger.error(
                "Unable to send email: %s",
                error
            )

            last_email_error_time = now

        return False

# ============================================================
# WORK-HOUR CHECK
# ============================================================

def monitoring_active():

    now = datetime.now(LOCAL_TZ)

    # Monday = 0
    # Friday = 4
    # Saturday = 5
    # Sunday = 6

    if now.weekday() > 4:
        return False

    if now.hour < WORK_START_HOUR:
        return False

    if now.hour >= WORK_END_HOUR:
        return False

    return True


# ============================================================
# DEXCOM CONNECTION
# ============================================================

def create_dexcom_connection():

    logger.info(
        "Connecting to Dexcom Share."
    )

    logger.info(
        "Dexcom region: %s",
        DEXCOM_REGION
    )

    try:

        dexcom = Dexcom(
            username=DEXCOM_USERNAME,
            password=DEXCOM_PASSWORD,
            region=DEXCOM_REGION
        )

        logger.info(
            "Dexcom connection created."
        )

        return dexcom

    except TypeError:

        # Compatibility fallback for older versions of
        # pydexcom that don't accept the region parameter.

        logger.warning(
            "pydexcom version does not accept region parameter. "
            "Retrying without region."
        )

        dexcom = Dexcom(
            username=DEXCOM_USERNAME,
            password=DEXCOM_PASSWORD
        )

        return dexcom


# ============================================================
# DEXCOM READING
# ============================================================

def get_current_reading(dexcom):

    try:

        reading = dexcom.get_current_glucose_reading()

        if reading is None:

            logger.warning(
                "Dexcom returned no current glucose reading."
            )

            return None

        return reading

    except Exception:

        logger.exception(
            "Error retrieving Dexcom reading."
        )

        raise


# ============================================================
# READING TIME
# ============================================================

def get_reading_time(reading):

    reading_time = reading.datetime

    if reading_time.tzinfo is None:

        # pydexcom returns a naive datetime.
        # Treat it as local time for our purposes.
        reading_time = reading_time.replace(
            tzinfo=LOCAL_TZ
        )

    else:

        reading_time = reading_time.astimezone(
            LOCAL_TZ
        )

    return reading_time

# ============================================================
# STALENESS
# ============================================================

def check_data_staleness(reading):

    global stale_alert_active

    reading_time = get_reading_time(
        reading
    )

    now = datetime.now(LOCAL_TZ)

    age_minutes = (
        now - reading_time
    ).total_seconds() / 60

    logger.info(
        "Reading age: %.1f minutes",
        age_minutes
    )

    if age_minutes > STALE_AFTER_MINUTES:

        if not stale_alert_active:

            subject = (
                f"{TRUE_NAME}'s Dexcom Data Is Stale"
            )

            message = (
                "DEXCOM DATA STALE\n\n"
                f"Last glucose reading: "
                f"{reading.value} mg/dL\n"
                f"Reading time: "
                f"{reading_time.strftime('%I:%M %p')}\n"
                f"Age: {age_minutes:.0f} minutes\n\n"
                "Dexcom data may not be reaching "
                "the Share service."
            )

            send_email(
                subject,
                message
            )

            stale_alert_active = True

    else:

        if stale_alert_active:

            send_email(
                f"{TRUE_NAME}'s Dexcom Data Has Been Restored",
                (
                    "DEXCOM DATA RESTORED\n\n"
                    f"Current glucose: "
                    f"{reading.value} mg/dL "
                    f"{reading.trend_arrow}\n"
                    f"Trend: "
                    f"{reading.trend_description}"
                )
            )

        stale_alert_active = False

# ============================================================
# ALERT PROCESSING
# ============================================================

def process_alerts(reading):

    global low_alert_active
    global urgent_low_alert_active
    global high_alert_active
    global rapid_rise_active
    global rapid_fall_active

    value = reading.value
    trend = reading.trend_description
    arrow = reading.trend_arrow

    # --------------------------------------------------------
    # URGENT LOW
    # --------------------------------------------------------

    if value < URGENT_LOW_ALERT:

        if not urgent_low_alert_active:

            send_email(
                f"{TRUE_NAME}'s Glucose Is URGENT LOW",
                (
                    "URGENT LOW GLUCOSE\n\n"
                    f"Current: {value} mg/dL {arrow}\n"
                    f"Trend: {trend}\n\n"
                    "Immediate attention recommended."
                )
            )

            urgent_low_alert_active = True

    elif value > 65:

        urgent_low_alert_active = False

    # --------------------------------------------------------
    # LOW
    # --------------------------------------------------------

    if (
        URGENT_LOW_ALERT
        <= value
        < LOW_ALERT
    ):

        if not low_alert_active:

            send_email(
                f"{TRUE_NAME}'s Glucose Is LOW",
                (
                    "LOW GLUCOSE\n\n"
                    f"Current: {value} mg/dL {arrow}\n"
                    f"Trend: {trend}"
                )
            )

            low_alert_active = True

    elif value > 80:

        low_alert_active = False

    # --------------------------------------------------------
    # HIGH
    # --------------------------------------------------------

    if value > HIGH_ALERT:

        if not high_alert_active:

            send_email(
                f"{TRUE_NAME}'s Glucose Is HIGH",
                (
                    "HIGH GLUCOSE\n\n"
                    f"Current: {value} mg/dL {arrow}\n"
                    f"Trend: {trend}"
                )
            )

            high_alert_active = True

    elif value < 220:

        high_alert_active = False

    # --------------------------------------------------------
    # RAPID RISE
    # --------------------------------------------------------

    rising_trends = {
        "SingleUp",
        "DoubleUp"
    }

    if reading.trend_direction in rising_trends:

        if not rapid_rise_active:

            send_email(
                f"{TRUE_NAME}'s Glucose Is On A RAPID RISE",
                (
                    "RAPID RISE\n\n"
                    f"Current: {value} mg/dL {arrow}\n"
                    f"Trend: {trend}"
                )
            )

            rapid_rise_active = True

    else:

        rapid_rise_active = False

    # --------------------------------------------------------
    # RAPID FALL
    # --------------------------------------------------------

    falling_trends = {
        "SingleDown",
        "DoubleDown"
    }

    if reading.trend_direction in falling_trends:

        if not rapid_fall_active:

            send_email(
                f"{TRUE_NAME}'s Glucose Is On A RAPID FALL",
                (
                    "RAPID FALL\n\n"
                    f"Current: {value} mg/dL {arrow}\n"
                    f"Trend: {trend}"
                )
            )

            rapid_fall_active = True

    else:

        rapid_fall_active = False


# ============================================================
# DAILY START MESSAGE
# ============================================================

def send_daily_start_message():

    global heartbeat_sent_date

    today = datetime.now(
        LOCAL_TZ
    ).date()

    if heartbeat_sent_date == today:

        return

    message = (
        f"Monitoring Of {TRUE_NAME}'s Dexcom Is Now Active\n\n"
        "Monitoring is active.\n\n"
        "Schedule:\n"
        "Monday-Friday\n"
        f"{WORK_START_HOUR:02d}:00 - "
        f"{WORK_END_HOUR:02d}:00\n\n"
        "Immediate glucose alerts are enabled.\n"
    )

    if send_email(
        f"{TRUE_NAME}'s Dexcom Is Now Actively Monitored",
        message
    ):

        heartbeat_sent_date = today

# ============================================================
# DAILY END MESSAGE
# ============================================================

def send_daily_end_message():

    now = datetime.now(LOCAL_TZ)

    message = (
        f"Finished Monitoring {TRUE_NAME}'s Dexcom For Today\n\n"
        f"Monitoring ended at "
        f"{now.strftime('%I:%M %p')}.\n\n"
        "Dexcom Follow remains responsible "
        "for notifications outside the "
        "configured work hours."
    )

    send_email(
        f"Finished Monitoring {TRUE_NAME}'s Dexcom For Today",
        message
    )


# ============================================================
# DEXCOM ERROR NOTIFICATION
# ============================================================

def report_dexcom_error(error):

    global last_dexcom_error_message
    global last_dexcom_error_time

    now = datetime.now(LOCAL_TZ)

    error_message = str(error)

    should_send = False

    if last_dexcom_error_time is None:

        should_send = True

    elif (
        now - last_dexcom_error_time
        >= timedelta(minutes=30)
    ):

        should_send = True

    elif (
        error_message
        != last_dexcom_error_message
    ):

        should_send = True

    if should_send:

        send_email(
            f"{TRUE_NAME}'s Dexcom Is Experiencing An Error",
            (
                f"{TRUE_NAME}'s Dexcom Is Experiencing An Error\n\n"
                f"{error_message}\n\n"
                "The monitor will continue "
                "trying to reconnect automatically."
            )
        )

        last_dexcom_error_time = now

        last_dexcom_error_message = (
            error_message
        )

# ============================================================
# MAIN LOOP
# ============================================================

def main():
    
    validate_configuration()

    logger.info(
        "============================================"
    )

    logger.info(
        "Dexcom Email Monitor starting."
    )

    logger.info(
        "Monitoring schedule: Monday-Friday "
        "%02d:00-%02d:00",
        WORK_START_HOUR,
        WORK_END_HOUR
    )

    logger.info(
        "Timezone: %s",
        TIMEZONE_NAME
    )

    logger.info(
        "Poll interval: %d seconds",
        POLL_INTERVAL_SECONDS
    )

    logger.info(
        "Notification mode: immediate email alerts only."
    )
    
    logger.info(
        "============================================"
    )

    dexcom = None

    previous_monitoring_state = False

    while True:

        try:

            currently_active = monitoring_active()

            #
            # Detect transition into work hours.
            #
            if currently_active and not previous_monitoring_state:

                logger.info(
                    "Work-hour monitoring started."
                )

                # Reconnect when entering the work window.
                dexcom = None

                send_daily_start_message()

            #
            # Detect transition out of work hours.
            #
            if (
                not currently_active
                and previous_monitoring_state
            ):

                logger.info(
                    "Work-hour monitoring ended."
                )
                
                # Send the workday-ended notification.
                send_daily_end_message()

            previous_monitoring_state = currently_active

            #
            # Outside work hours
            #
            if not currently_active:

                time.sleep(60)

                continue

            #
            # Establish Dexcom connection.
            #
            if dexcom is None:

                try:

                    dexcom = create_dexcom_connection()

                except Exception as error:

                    logger.exception(
                        "Unable to connect to Dexcom."
                    )

                    report_dexcom_error(error)

                    time.sleep(
                        POLL_INTERVAL_SECONDS
                    )

                    continue

            #
            # Retrieve current reading.
            #
            try:

                reading = get_current_reading(
                    dexcom
                )

            except Exception as error:

                logger.exception(
                    "Dexcom request failed."
                )

                report_dexcom_error(error)

                # Force a fresh connection on the next
                # iteration.
                dexcom = None

                time.sleep(
                    POLL_INTERVAL_SECONDS
                )

                continue

            #
            # No reading.
            #
            if reading is None:

                logger.warning(
                    "No Dexcom reading returned."
                )

                time.sleep(
                    POLL_INTERVAL_SECONDS
                )

                continue

            #
            # Log reading.
            #
            logger.info(
                "Glucose=%s mg/dL | Trend=%s | "
                "Direction=%s | Arrow=%s",
                reading.value,
                reading.trend_description,
                reading.trend_direction,
                reading.trend_arrow
            )
            
            check_data_staleness(
                reading
            )

            #
            # Only process alerts if the reading itself
            # is reasonably current.
            #
            reading_time = get_reading_time(
                reading
            )

            reading_age = (
                datetime.now(LOCAL_TZ)
                - reading_time
            ).total_seconds() / 60

            if reading_age <= STALE_AFTER_MINUTES:

                #
                # Alerts
                #
                process_alerts(
                    reading
                )

            else:

                logger.warning(
                    "Reading is stale; "
                    "skipping normal alerts."
                )

            #
            # Wait until the next polling cycle.
            #
            time.sleep(
                POLL_INTERVAL_SECONDS
            )

        except KeyboardInterrupt:

            logger.info(
                "Shutdown requested."
            )

            break

        except Exception as error:

            logger.exception(
                "Unexpected error in main loop."
            )

            report_dexcom_error(error)

            # Don't let an unexpected exception kill
            # the monitor permanently.
            time.sleep(60)


# ============================================================
# ENTRY POINT
# ============================================================

if __name__ == "__main__":

    main()
