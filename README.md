# Dexcom Email Alerts (Docker)

A small Docker application that checks Dexcom Share for glucose readings and emails alerts during configured hours. Designed for parents and caregivers who want an **additional** way to receive notifications at a computer.

**Important:** This is an unofficial, supplemental tool. It is **not** a medical device or a substitute for the Dexcom G7 app, Dexcom Follow, their official alerts, or an emergency response plan. Email and internet delivery can be delayed or fail. Do not rely on it as the only way to detect urgent glucose events.

This project was made using chatgpt.  I am not as well versed with Python, and needed the script to work properly.

## What you'll need

- A working Dexcom account with readings available through **Dexcom Share**.
- A Gmail account to **send** alert emails, and an email address to **receive** them (they can be the same address).
- A computer or NAS that can run Docker and stay powered on during monitoring hours.
- The project files: `dexcom_monitor.py`, `Dockerfile`, and `docker-compose.yml`.

> These steps assume the supplied Python and Docker files use the environment variable names shown below. The maintainer should check the published files against this README before sharing.

## 1. Set up Gmail to send emails

1. Sign in to the Google account that will **send** the alerts.
2. Open [Google Account Security](https://myaccount.google.com/security) and enable **2-Step Verification** if it is not already enabled.
3. Open [Google App Passwords](https://myaccount.google.com/apppasswords). If the option is unavailable, your account or organization may not permit App Passwords.
4. Create an App Password named something like **Dexcom Docker**.
5. Copy the generated 16-character password. **Use this App Password, not your normal Gmail password**, in the configuration below. Remove any spaces when pasting it.

The SMTP settings are `smtp.gmail.com`, port `587`, with TLS/STARTTLS. You do **not** need to enable “less secure apps.”

## 2. Install Docker

- **Windows or Mac:** Install [Docker Desktop](https://www.docker.com/products/docker-desktop/), start it, and wait until it says Docker is running.
- **Linux or a NAS:** Install Docker Engine and the **Docker Compose** plugin using your device's documentation. On a NAS, you may already have a Docker/Container Manager application.

Open a terminal (Windows: PowerShell; Mac/Linux: Terminal) and verify:

```bash
docker compose version
```

## 3. Put the project files in one folder

Create a folder named `dexcom-email-alerts` and put these files inside:

```text
dexcom-email-alerts/
├── dexcom_monitor.py
├── Dockerfile
├── docker-compose.yml
└── .env                 # Create this in Step 4; keep it private
```

Open a terminal **inside that folder**. All commands below run there.

## 4. Create your private `.env` file

Create a plain-text file named **`.env`** (not `.env.txt`) alongside the other files. Paste this example and replace the sample values:

```dotenv
# Dexcom Share login (not your Gmail login)
DEXCOM_USERNAME=your_dexcom_username
DEXCOM_PASSWORD=your_dexcom_password
DEXCOM_REGION=us

# Name displayed in email subjects
TRUE_NAME=Child Name

# Gmail account sending the alerts
SMTP_SERVER=smtp.gmail.com
SMTP_PORT=587
SMTP_USERNAME=youraddress@gmail.com
SMTP_PASSWORD=your_16_character_google_app_password
EMAIL_FROM=youraddress@gmail.com

# Where alerts should arrive
EMAIL_TO=recipient@example.com

# Schedule and alert settings
TZ=America/New_York
POLL_INTERVAL_SECONDS=300
WORK_START_HOUR=7
WORK_END_HOUR=16
URGENT_LOW_ALERT=55
LOW_ALERT=70
HIGH_ALERT=250
STALE_AFTER_MINUTES=20
```

**Customize:**

- `TRUE_NAME` is the friendly name shown in email subjects. It is **not** used to log in to Dexcom.
- `EMAIL_TO` is the destination address. If your script supports multiple recipients, separate them with commas.
- `TZ` is your time zone, such as `America/Chicago`, `America/Denver`, or `America/Los_Angeles`.
- The example schedule is **Monday–Friday, 7:00 AM–4:00 PM**. Hours use a 24-hour clock; `16` means 4 PM.
- Alert thresholds are **example configuration values**, not medical recommendations. Only change them in accordance with your family's established care plan.

**Keep `.env` private.** It contains account credentials. Never upload it to GitHub or share it in screenshots.

## 5. Start the container

From the project folder, run:

```bash
docker compose up -d --build
```

The first run may take a few minutes while Docker downloads and installs dependencies. To check that it started:

```bash
docker compose ps
```

To watch the application logs:

```bash
docker compose logs -f
```

Press **Ctrl+C** to stop viewing logs; this does **not** stop the container.

**Note:** If you're testing outside the configured weekday work hours, the monitor may correctly wait until its next scheduled window. You may temporarily adjust the work hours in `.env` and recreate the container to test. An alert email is sent only when a qualifying condition occurs; a normal reading should not produce an alert.

## 6. Everyday commands

Run these from the same project folder:

| Task | Command |
|---|---|
| View logs | `docker compose logs -f` |
| Restart | `docker compose restart` |
| Stop | `docker compose down` |
| Start again | `docker compose up -d` |
| Apply changes to `.env` | `docker compose up -d --force-recreate` |
| Apply changes to Python or Dockerfile | `docker compose up -d --build` |

## Troubleshooting

- **No emails:** Check `docker compose logs -f`. Confirm you're inside the monitoring schedule and that an alert condition actually occurred. Check spam/junk folders.
- **Gmail authentication error:** Use the **App Password**, not your normal Google password. Verify the sending address and that App Passwords are permitted on your account.
- **Dexcom login error:** Check the Dexcom **username**, password, and region. These are separate from Gmail credentials. Confirm readings are being shared through Dexcom Share.
- **Changes aren't taking effect:** After editing `.env`, recreate the container. After editing Python, rebuild the image (see the table above).
- **Docker command fails:** Make sure Docker is installed and running, and that the terminal is open in the folder containing `docker-compose.yml`.
- **Readings appear delayed or missing:** Check that the phone is uploading to Dexcom Share and has working internet access. This application cannot fix upstream Dexcom sharing problems.

## Privacy and safety

This project accesses sensitive glucose information and sends it by email. Use trusted recipient addresses, secure the host computer, and limit who can access Docker logs. Email is not guaranteed to be immediate, private end-to-end, or continuously available. Continue using official Dexcom monitoring and follow the guidance of the child's healthcare team.
