"""
Работа с Google Таблицей.
Таблица должна содержать 4 листа (вкладки внизу):
  - Reports    (Дата, Username, Имя, Предмет, Текст)
  - FAQ        (Вопрос, Ответ)
  - Reminders  (Дата, Время, Текст, Отправлено)
  - Users      (chat_id, Имя)
Заголовки (первая строка) создаются автоматически при первом запуске,
если их ещё нет.
"""

import os
import json
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

_client = None
_sheet = None


def _connect():
    """Ленивое подключение к Google Sheets (один раз за всё время работы бота).

    Поддерживает два способа передать ключ сервисного аккаунта:
      1. GOOGLE_CREDENTIALS_JSON — всё содержимое credentials.json одной строкой
         в переменной окружения (удобно для Railway/облака).
      2. GOOGLE_CREDENTIALS_FILE — путь к файлу credentials.json на диске
         (удобно для локального запуска).
    Если задано первое — используется оно, иначе ищется файл.
    """
    global _client, _sheet
    if _sheet is not None:
        return _sheet

    sheet_id = os.getenv("GOOGLE_SHEET_ID")
    creds_json = os.getenv("GOOGLE_CREDENTIALS_JSON")

    if creds_json:
        info = json.loads(creds_json)
        creds = Credentials.from_service_account_info(info, scopes=SCOPES)
    else:
        creds_file = os.getenv("GOOGLE_CREDENTIALS_FILE", "credentials.json")
        creds = Credentials.from_service_account_file(creds_file, scopes=SCOPES)

    _client = gspread.authorize(creds)
    _sheet = _client.open_by_key(sheet_id)
    return _sheet


def _get_or_create_tab(title, headers):
    sheet = _connect()
    try:
        ws = sheet.worksheet(title)
    except gspread.WorksheetNotFound:
        ws = sheet.add_worksheet(title=title, rows=1000, cols=len(headers))
        ws.append_row(headers)
        return ws

    # если лист пустой — добавляем заголовки
    if not ws.get_all_values():
        ws.append_row(headers)
    return ws


# ---------- Отчёты ----------

def add_report(username, full_name, subject, text):
    ws = _get_or_create_tab("Reports", ["Дата", "Username", "Имя", "Предмет", "Текст"])
    ws.append_row([
        datetime.now().strftime("%Y-%m-%d %H:%M"),
        username or "-",
        full_name or "-",
        subject,
        text,
    ])


# ---------- FAQ ----------

def get_faq():
    """Возвращает список (вопрос, ответ) из листа FAQ."""
    ws = _get_or_create_tab("FAQ", ["Вопрос", "Ответ"])
    rows = ws.get_all_values()[1:]  # пропускаем заголовок
    return [(r[0], r[1]) for r in rows if len(r) >= 2 and r[0].strip()]


# ---------- Напоминания ----------

def add_reminder(date_str, time_str, text):
    ws = _get_or_create_tab("Reminders", ["Дата", "Время", "Текст", "Отправлено"])
    ws.append_row([date_str, time_str, text, "нет"])


def get_due_reminders(now: datetime):
    """Возвращает список (номер_строки, текст) напоминаний, время которых наступило и которые ещё не отправлены."""
    ws = _get_or_create_tab("Reminders", ["Дата", "Время", "Текст", "Отправлено"])
    rows = ws.get_all_values()
    due = []
    for i, row in enumerate(rows[1:], start=2):  # start=2: строка 1 — заголовок
        if len(row) < 4:
            continue
        date_s, time_s, text, sent = row[0], row[1], row[2], row[3]
        if sent.strip().lower() == "да":
            continue
        try:
            dt = datetime.strptime(f"{date_s} {time_s}", "%Y-%m-%d %H:%M")
        except ValueError:
            continue
        if dt <= now:
            due.append((i, text))
    return due, ws


def mark_reminder_sent(ws, row_number):
    ws.update_cell(row_number, 4, "да")


# ---------- Пользователи ----------

def register_user(chat_id, full_name):
    ws = _get_or_create_tab("Users", ["chat_id", "Имя"])
    ids = ws.col_values(1)
    if str(chat_id) not in ids:
        ws.append_row([str(chat_id), full_name or "-"])


def get_all_user_ids():
    ws = _get_or_create_tab("Users", ["chat_id", "Имя"])
    return [row[0] for row in ws.get_all_values()[1:] if row and row[0].strip()]
