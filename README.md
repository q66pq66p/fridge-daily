# Fridge AI v3 - UNKNOWN 중심 관리

## 핵심 변경
1. 기존 YOLO FOOD / CONTAINER 탐지 유지 및 클래스 확장
2. YOLO 미검출 영역은 `UNKNOWN(UTxxxxxx)`으로 지속 추적
3. YOLO가 용기를 인식했지만 내부 식재료는 모르는 경우
   `CONTENT_UNKNOWN(CUxxxxxx)`으로 별도 지속 추적
4. SQLite에서 최초 발견일/마지막 발견일/관찰 횟수 관리
5. 기본 7일 이상 + 2회 이상 관찰된 대상만 장기보관 알림 후보
6. 현재 사진에 실제 보이는 대상만 Bounding Box로 표시
7. Telegram 전송용 한글 메시지와 표시 이미지를 생성
8. 같은 대상은 기본 7일 간격으로 재알림
9. Ollama / Recipe 기능 없음

## 실행
`images/test2_fridge03.jpg`를 준비한 후 프로젝트 루트에서:

    python app.py

## 테스트 시
`config.py`에서 `ALERT_AFTER_DAYS = 1`로 두면 당일 테스트가 쉽습니다.
운영 시에는 다시 7 이상으로 설정하세요.

## ID
- UT000001: YOLO도 식별하지 못한 영역
- CU000001: 용기는 식별했지만 내부 내용물은 미확인

## Telegram 연결
`src/services/telegram_alert.py`의 `send_fridge_alert()`를
기존 Telegram 사진 처리 handler에서 호출하면 됩니다.
