from collections.abc import Iterator
from contextlib import AbstractContextManager
from typing import Protocol

from ai_trader.domain.profile import RiskPolicy, UserProfile


class ProfileRepository(Protocol):
    def get(self) -> UserProfile | None: ...

    def current_policy(self) -> RiskPolicy | None: ...

    def save(self, profile: UserProfile, policy: RiskPolicy) -> None: ...


class UnitOfWork(Protocol):
    profiles: ProfileRepository

    def __enter__(self) -> "UnitOfWork": ...

    def __exit__(self, exc_type: object, exc: object, traceback: object) -> None: ...


class UnitOfWorkFactory(Protocol):
    def __call__(self) -> AbstractContextManager[UnitOfWork]: ...


SessionIterator = Iterator[object]

