# FocusFlow – Smart Student Focus Tracker

FocusFlow is a smart student productivity web app built using **Flask + HTML + CSS + JavaScript + SQLite**.

It helps students track their study sessions, manage reminders, analyze subject-wise study patterns, and get support from an AI assistant.

---

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
