# GLIMPRINT System Documentation

This repository contains the source code for the GLIMPRINT website, a platform for sharing news, seminars, workshops, and publications.

## System Overview

The application is built using **FastAPI** (Python) and renders HTML templates using **Jinja2**. It uses a lightweight database layer that supports both **SQLite** (for local development) and **Turso** (libsql) for production.

Key components:
- **FastAPI App**: Handles routing, templating, and logic.
- **Database**: SQLite (Local) / Turso (Production).
- **Admin System**: Secure dashboard for content management and approval.
- **Mailing System**: SMTP-based mailing for announcements.

## Prerequisites

- Python 3.9+
- `uv` (recommended for dependency management) or `pip`
- A Turso account (for production database)
- A Vercel account (for deployment)

## Local Development Setup

Follow these steps to set up the project locally.

### 1. Clone the Repository
```bash
git clone <repository-url>
cd glimprint
```

### 2. Install Dependencies
Using `uv`:
```bash
uv sync
```
Or using `pip`:
```bash
pip install -r requirements.txt
```

### 3. Environment Configuration (.env)
For local development, we use a `.env` file to store sensitive information. This file is **ignored by Git** to prevent leaking secrets.

Create a file named `.env` in the root directory:
```bash
touch .env
```
Add the following content to `.env`:

```ini
# Security
SECRET_KEY=dev_secret_key_change_me_locally

# Database (Optional for local dev, needed if testing migration)
# TURSO_DATABASE_URL=...
# TURSO_AUTH_TOKEN=...

# Mailing (Optional for local dev)
# SMTP_SERVER=localhost
# SMTP_PORT=1025
# SMTP_USER=
# SMTP_PASSWORD=

```

### 4. Configure Email (Optional)
To send announcements, configure your SMTP server details in `.env`:
```
SMTP_SERVER=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=your-email@gmail.com
SMTP_PASSWORD=your-app-password
```
**Important Limitation**:
- The application uses `SMTP_USER` to authenticate and send emails.
- Current implementation sends emails "From" the currently logged-in administrator's email address.
- Most email providers (like Gmail) will rewrite the sender to match `SMTP_USER` or block the email if they don't match.
- **Recommendation**: Ensure the administrator sending the announcements is the same one configured in `SMTP_USER`.

**Note:** If `TURSO_DATABASE_URL` is not set, the app defaults to a local SQLite database at `db/glimprint.db`.

### 5. Initialize or Update Local Database
Run the schema update script to create or update your local SQLite database:
```bash
python scripts/update_schema.py
```
**About this script:**
- **Initial Setup**: If no database exists, it creates `db/glimprint.db` with the complete table structure.
- **Updates**: If the database already exists, it non-destructively updates the schema (e.g., adding missing columns) without deleting your data. Run this whenever you pull code changes that might affect the database.

### 6. Manage Admin Users
The `scripts/create_admin.py` script manages admin credentials.

**Create a new admin:**
```bash
# Usage: uv run python scripts/create_admin.py <username> <password> <email>
uv run python scripts/create_admin.py admin ChangeMe123! admin@glimprint.org
```

**Update existing admin password/email:**
```bash
uv run python scripts/create_admin.py admin NewPassword123! newemail@glimprint.org --update
```

**Delete an admin:**
```bash
uv run python scripts/create_admin.py admin --delete
```


### 7. Run the Application (Development)
To run the application in the development environment with hot-reloading enabled:

```bash
uv run uvicorn app.main:app --reload
# OR
uvicorn app.main:app --reload
```
Visit http://127.0.0.1:8000.

---

## Turso Database Setup (Production)

Follow these steps to set up your production database on Turso.

1.  **Sign Up & Install CLI**:
    - Go to [turso.tech](https://turso.tech) and sign up.
    - Install the Turso CLI:
        - **MacOS/Linux**: `curl -sSfL https://get.tur.so/install.sh | bash`
        - **Windows**: `winget install turso`

2.  **Login**:
    ```bash
    turso auth login
    ```

3.  **Create a Database**:
    ```bash
    turso db create glimprint-db
    ```

4.  **Get Connection URL**:
    ```bash
    turso db show glimprint-db --url
    ```
    *Copy this URL (e.g., `libsql://glimprint-db-user.turso.io`).*

5.  **Get Authentication Token**:
    ```bash
    turso db tokens create glimprint-db
    ```
    *Copy this long string. This is your `TURSO_AUTH_TOKEN`.*

6.  **Migrate Local Data to Turso**:
    Now that you have the credentials, you can migrate your local schema and data to Turso.
    
    In your terminal (with the `.env` file or exporting variables):
    
    **Option A: Using .env (Recommended for local)**
    Ensure your `.env` file has `TURSO_DATABASE_URL` and `TURSO_AUTH_TOKEN` set.

    **Option B: Manually Exporting Variables**
    ```bash
    export TURSO_DATABASE_URL="your-turso-url"
    export TURSO_AUTH_TOKEN="your-turso-token"
    ```

    Then run the migration script:
    ```bash
    uv run python scripts/migrate_to_turso.py
    ```
    This script will:
    1. Read your local `db/glimprint.db`.
    2. Connect to the Turso DB.
    3. Create tables if they don't exist.
    4. Copy all data (using `INSERT OR REPLACE` to avoid duplicates).

---

## Deployment to Vercel

We deploy to Vercel using the `vercel.json` configuration. Vercel will act as the production environment.

**Important:** Vercel **does not** read the `.env` file committed to the repository (which should be ignored anyway). You must set environment variables in the Vercel Project Settings.

### Step-by-Step Deployment

1.  **Push to GitHub**: Ensure your code is pushed to your GitHub repository.

2.  **Import Project in Vercel**:
    - Go to [vercel.com](https://vercel.com) and log in.
    - Click **"Add New..."** -> **"Project"**.
    - Import your `glimprint` git repository.

3.  **Configure Project**:
    - **Framework Preset**: select "Other".
    - **Root Directory**: `./` (default).

4.  **Set Environment Variables**:
    Since `.env` is not uploaded, you must **manually add** the following keys and values in the Vercel Project Settings (under **Settings** -> **Environment Variables**). Use the Turso credentials you generated earlier:

    | Key | Value |
    |-----|-------|
    | `TURSO_DATABASE_URL` | `libsql://glimprint-db-user.turso.io` |
    | `TURSO_AUTH_TOKEN` | `your-long-jwt-token` |
    | `SECRET_KEY` | (Generate a strong random string) |
    | `SMTP_SERVER` | Your SMTP Server (e.g., `smtp.gmail.com`) |
    | `SMTP_PORT` | Your SMTP Port (e.g., `587`) |
    | `SMTP_USER` | Your email address |
    | `SMTP_PASSWORD` | Your email app password |


5.  **Deploy**:
    - Click **"Deploy"**.
    - Vercel will build the Python app and deploy it.

6.  **Verify**:
    - Visit the deployment URL.
    - Go to `/admin/login` and try to log in with the admin credentials you migrated (or create a new one if you didn't migrate user data).

### Troubleshooting Vercel

- **Database Errors**: Check the Function Logs in Vercel. If connection fails, double-check `TURSO_DATABASE_URL` and `TURSO_AUTH_TOKEN`.
- **Static Files**: Ensure `vercel.json` is correctly routing `/static/*`.
- **Mailing**: If emails fail, check SMTP credentials. For Gmail, you often need an "App Password" if 2FA is enabled.

---

## Admin Usage

1.  **Access**: Navigate to `/admin/login`.
2.  **Dashboard**: View pending approvals and quick links.
3.  **Approvals**:
    - Public submissions (News, Seminars, etc.) appear in "Pending Approvals".
    - Click "Approve" to publish them live.
4.  **Mailing**:
    - **Manage Contacts**: Add people to the mailing list.
    - **Send Announcement**: Send a broadcast email to all contacts.
    - **JSON Send**: Send emails using a custom JSON list (useful for importing existing lists).
