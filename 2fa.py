import os
import re
import time
import sqlite3
import subprocess
import threading
import pyperclip
import logging
from watchdog.observers.polling import PollingObserver  # PollingObserver 사용
from watchdog.events import FileSystemEventHandler

# 로깅 설정 (환경변수로 레벨 제어, 기본값: INFO)
log_level = os.environ.get('LOG_LEVEL', 'INFO')
logging.basicConfig(level=getattr(logging, log_level, logging.INFO), format='[%(levelname)s] %(message)s')

# 상수 정의
DB_PATH = os.path.expanduser('~/Library/Messages/chat.db')
MESSAGES_DIR = os.path.expanduser("~/Library/Messages")
CLIPBOARD_CLEAR_TIMEOUT = 60  # 클립보드 자동 정리 시간 (초)
AUTH_KEYWORDS = ['인증', '확인', '코드', 'code', 'verify', 'verification', 'OTP', '번호']

if not os.path.exists(DB_PATH):
    logging.error("메시지 데이터베이스를 찾을 수 없습니다. 경로를 확인하세요.")
    exit(1)

# 마지막 메시지의 rowid를 저장하는 전역 변수
latest_rowid = None

def show_notification(title, message):
    """macOS 알림 센터를 통해 알림을 표시합니다."""
    logging.debug(f"알림 표시: 제목={title}, 내용={message}")
    try:
        safe_title = title.replace('"', '\\"')
        safe_message = message.replace('"', '\\"')
        script = f'display notification "{safe_message}" with title "{safe_title}"'
        subprocess.run(['osascript', '-e', script], capture_output=True)
    except Exception as e:
        logging.error(f"알림 표시 실패: {e}")

def copy_with_expiry(code, timeout=CLIPBOARD_CLEAR_TIMEOUT):
    """인증번호를 클립보드에 복사하고, 일정 시간 후 자동으로 정리합니다."""
    pyperclip.copy(code)
    def clear():
        if pyperclip.paste() == code:
            pyperclip.copy('')
            logging.debug(f"클립보드에서 인증번호 {code} 자동 정리됨")
    threading.Timer(timeout, clear).start()

def process_new_message():
    """새로운 메시지를 처리하고 인증번호를 클립보드에 복사합니다."""
    global latest_rowid
    logging.debug("process_new_message 호출됨")
    try:
        with sqlite3.connect(f'file:{DB_PATH}?mode=ro', uri=True) as conn:
            cur = conn.cursor()
            cur.execute("SELECT rowid, text FROM message ORDER BY date DESC LIMIT 1")
            row = cur.fetchone()

            if row:
                rowid, text = row
                logging.debug(f"rowid: {rowid}, 메시지 내용: {text}")

                # 이전에 처리한 메시지인지 확인
                if latest_rowid is None or latest_rowid != rowid:
                    latest_rowid = rowid

                    # text가 문자열이며 공백만이 아닌지 확인
                    if isinstance(text, str) and text.strip():
                        # 인증번호 관련 키워드가 포함된 메시지에서만 추출
                        if any(keyword.lower() in text.lower() for keyword in AUTH_KEYWORDS):
                            match = re.search(r'\b\d{4,8}\b', text)
                            if match:
                                code = match.group()
                                logging.debug(f"클립보드로 복사할 인증번호: {code}")
                                copy_with_expiry(code)
                                show_notification("2FA 인증번호", f"인증번호 {code}가 클립보드에 복사되었습니다.")
                            else:
                                logging.debug("인증번호가 메시지에서 발견되지 않았습니다.")
                        else:
                            logging.debug("인증번호 관련 키워드가 없는 메시지입니다. 건너뜁니다.")
                    else:
                        logging.debug("메시지 내용이 None이거나 유효한 문자열이 아닙니다. 처리 건너뜁니다.")
            else:
                logging.debug("데이터베이스에서 메시지를 찾을 수 없습니다.")
    except sqlite3.OperationalError as e:
        logging.error(f"데이터베이스 접근 오류: {e}")
        show_notification("오류", "데이터베이스 접근 권한이 없습니다.")
    except sqlite3.Error as e:
        logging.error(f"데이터베이스 읽기 오류: {e}")
    except Exception as e:
        logging.error(f"예기치 않은 오류 발생: {e}")

class DatabaseChangeHandler(FileSystemEventHandler):
    def __init__(self):
        super().__init__()
        self._timer = None
        self._debounce_sec = 0.5

    def on_modified(self, event):
        logging.debug(f"감지된 이벤트: {event.event_type}, 파일: {event.src_path}")
        # 데이터베이스 파일 또는 WAL 파일 변경 감지
        if event.src_path in [DB_PATH, DB_PATH + '-wal']:
            logging.debug("데이터베이스 변경 감지됨. 디바운싱 중...")
            if self._timer:
                self._timer.cancel()
            self._timer = threading.Timer(self._debounce_sec, process_new_message)
            self._timer.start()

def main():
    observer = PollingObserver()
    try:
        observer.schedule(DatabaseChangeHandler(), path=MESSAGES_DIR, recursive=False)
        logging.debug("프로그램 초기화 중...")
        process_new_message()
        logging.debug("메시지 데이터베이스 변경 감지 중...")
        observer.start()
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        logging.info("프로그램이 종료됩니다.")
    except PermissionError as e:
        logging.error(f"파일 접근 권한 오류: {e}")
        show_notification("오류", "파일 접근 권한이 없습니다. 시스템 환경설정에서 전체 디스크 접근 권한을 확인하세요.")
    except Exception as e:
        logging.error(f"예기치 않은 오류 발생: {e}")
    finally:
        if observer.is_alive():
            observer.stop()
            try:
                observer.join()
            except RuntimeError as e:
                logging.error(f"join 중 예외 발생: {e}")
        else:
            logging.debug("Observer thread가 시작되지 않았으므로 join을 호출하지 않습니다.")

if __name__ == '__main__':
    main()
