from app.memory.privacy import should_reject_long_term_memory


def test_otp_like_content_is_not_long_term_memory() -> None:
    assert should_reject_long_term_memory("رمز التحقق 123456")
    assert not should_reject_long_term_memory("يريد تجديد اشتراكه السنوي")
