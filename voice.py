"""목소리(TTS) 자리 비움. 이 배포판에는 음성 기능이 들어 있지 않습니다.
위젯 본체가 voice 모듈을 부르기 때문에, 아무것도 하지 않는 빈 껍데기만 둡니다."""
VOICED = ()          # 목소리가 있는 캐릭터 목록 (없음)
VOLUME = 0.0


def enabled():
    return False


def set_enabled(on):
    pass


def set_volume(v):
    pass


def speak(text, face=None, char=None):
    pass


def warmup(char, done):
    done(False)


def shutdown():
    pass
