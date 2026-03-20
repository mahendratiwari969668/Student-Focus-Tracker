# FocusFlow – Smart Student Focus Tracker

FocusFlow is a smart student productivity web app built using **Flask + HTML + CSS + JavaScript + SQLite**.

It helps students track their study sessions, manage reminders, analyze subject-wise study patterns, and get support from an AI assistant.


----------------------------____________________________-------------------------------------------______________________
## ⚠️ IMPORTANT THINGS

### 1) AI Assistant Setup (Required)
If you want to use the **FLOWBOT AI Assistant**, you must create your **own API key** and save it inside a `.env` file.

Example:

env
SAMBANOVA_API_KEY=your_api_key_here
SAMBANOVA_API_URL=https://api.sambanova.ai/v1/chat/completions
SAMBANOVA_MODEL=Meta-Llama-3.1-8B-Instruct

Without your own API key, the AI feature will not work.

2) Forgot Password / Reset Password
If you forget your password, click on Forgot Password and reset it using OTP verification.
3) OTP by Default (Terminal Mode)
By default, if email credentials are not configured, the OTP will be shown in the terminal / VS Code console.
So if you are running the project locally and you do not set email credentials, check the terminal to see the OTP.
4) OTP in Email (Optional)
If you want the OTP to be sent directly to your email inbox, you must add your own Gmail address and Gmail App Password inside the .env file.
Example:
Env
Copy code
SENDER_EMAIL=your_gmail_address_here
SENDER_PASSWORD=your_gmail_app_password_here
5) How to get Gmail App Password
To get a Gmail App Password:
Turn on 2-Step Verification in your Google account
Then go to App Passwords
Generate a new app password for Mail
Use that generated password in .env
⚠️ Do NOT use your normal Gmail password
You must use the App Password generated after enabling 2-Factor Authentication / 2-Step Verification.
6) Security Warning
Never upload your .env file to GitHub because it contains:
API keys
Gmail email
Gmail app password
Secret keys


----------------------------------________-----------------------------____________--------------------------------------

## 🚀 Features

### 🔐 Authentication System
- User registration
- User login
- Logout
- Forgot password with OTP verification
- Password reset system
- Gmail SMTP support using `.env`

### ⏱️ Live Focus Timer
- Real-time study timer
- Exact second tracking
- No fake rounding
- Save directly as a study session
- Track distractions during session

### 📝 Manual Session Entry
- Add study session manually (backup option)
- Custom date and time support
- Subject-wise entry
- Distraction count support

### 📊 Subject-wise Analytics
- Total study time per subject
- Total sessions per subject
- Total distractions per subject
- Top studied subject
- Progress bars for visual comparison

### 🎯 Daily Goal System
- Set daily goal in hours, minutes, and seconds
- See goal progress percentage
- Dynamic progress bar

### 🔥 Streak Tracking
- Current streak
- Longest streak
- Last 7 days study chart
- Best study day

### ⏰ Smart Reminder System
- Add reminders with title, message, date, and time
- Subject-based reminders
- Once / Daily / Weekly reminder type
- Reminder popup when due
- Snooze reminder
- Mark reminder as done
- Delete reminder

### 🤖 FLOWBOT AI Assistant
- Floating AI robot assistant
- Helps explain study paragraphs simply
- Gives subject suggestions
- Provides focus tips
- Helps with coding errors
- Can analyze tracker data
- Uses Sambanova API

---

## 🛠️ Tech Stack

- **Backend:** Python, Flask
- **Frontend:** HTML, CSS, JavaScript
- **Database:** SQLite
- **Authentication:** Flask Sessions + Werkzeug Password Hashing
- **Email:** Gmail SMTP
- **AI:** Sambanova API

---

## 📁 Project Structure

```bash
FocusFlow/
│
├── app.py
├── .env
├── .gitignore
├── README.md
│
├── templates/
│   ├── index.html
│   ├── login.html
│   ├── register.html
│   ├── forgot_password.html
│   ├── verify_otp.html
│   ├── reset_password.html
│   └── dashboard.html
│
├── static/
│   └── (optional css/js files if used)
│
└── focusflow.db   # auto-created (should NOT be pushed)
