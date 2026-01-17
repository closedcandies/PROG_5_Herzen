import json
from random import randint

from settings import settings
from utils.clients.mailing import MailingClient


class EmailVerificationService:
    PREFIX = "verify-email"

    def __init__(self, redis_client):
        self.redis = redis_client

    @classmethod
    def _verify_key(cls, email: str) -> str:
        return f"{cls.PREFIX}:{email}"

    @classmethod
    def _attempts_key(cls, email: str) -> str:
        return f"{cls.PREFIX}:{email}:attempts"

    def _generate_code(self) -> str:
        code_len = settings.verification.code_length
        return f"{randint(0, 10**code_len - 1):0{code_len}d}"

    async def send_code(self, email: str, hashed_password: str, name: str, mailer: MailingClient):
        code = self._generate_code()
        payload = {
            "code": code,
            "password": hashed_password,
            "name": name,
        }
        self.redis.setex(
            self._verify_key(email),
            settings.verification.ttl_seconds,
            json.dumps(payload),
        )
        self.redis.delete(self._attempts_key(email))

        await mailer.send_mail(
            to=email,
            subject="Код подтверждения",
            message=f"Ваш код подтверждения: {code}",
        )

    def get_payload(self, email: str) -> dict | None:
        raw = self.redis.get(self._verify_key(email))
        return json.loads(raw) if raw else None

    def record_attempt(self, email: str) -> int:
        attempts = self.redis.incr(self._attempts_key(email))
        self.redis.expire(self._attempts_key(email), settings.verification.ttl_seconds)
        return attempts

    def clear(self, email: str) -> None:
        self.redis.delete(self._verify_key(email))
        self.redis.delete(self._attempts_key(email))

