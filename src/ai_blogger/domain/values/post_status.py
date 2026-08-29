"""Жизненный цикл поста"""

from __future__ import annotations

from enum import StrEnum
from typing import TYPE_CHECKING, Final

from ai_blogger.domain.errors import IllegalTransitionError

if TYPE_CHECKING:
    from collections.abc import Mapping


class PostStatus(StrEnum):
    DRAFT = "draft"
    NEEDS_REVIEW = "needs_review"
    APPROVED = "approved"
    PUBLISHED = "published"
    REJECTED = "rejected"
    GENERATION_FAILED = "generation_failed"
    PUBLICATION_FAILED = "publication_failed"

    @property
    def is_final(self) -> bool:
        return not ALLOWED_TRANSITIONS[self]

    def can_move_to(self, target: PostStatus) -> bool:
        return target in ALLOWED_TRANSITIONS[self]

    def ensure_can_move_to(self, target: PostStatus) -> None:
        if not self.can_move_to(target):
            raise IllegalTransitionError(
                f"пост нельзя перевести из «{self}» в «{target}»; "
                f"из «{self}» допустимо: {_describe(ALLOWED_TRANSITIONS[self])}"
            )


ALLOWED_TRANSITIONS: Final[Mapping[PostStatus, frozenset[PostStatus]]] = {
    PostStatus.DRAFT: frozenset({PostStatus.NEEDS_REVIEW, PostStatus.GENERATION_FAILED}),
    PostStatus.NEEDS_REVIEW: frozenset(
        {PostStatus.APPROVED, PostStatus.REJECTED, PostStatus.DRAFT}
    ),
    PostStatus.APPROVED: frozenset(
        {PostStatus.PUBLISHED, PostStatus.PUBLICATION_FAILED, PostStatus.NEEDS_REVIEW}
    ),
    PostStatus.GENERATION_FAILED: frozenset({PostStatus.DRAFT}),
    PostStatus.PUBLICATION_FAILED: frozenset({PostStatus.APPROVED}),
    PostStatus.PUBLISHED: frozenset(),
    PostStatus.REJECTED: frozenset(),
}


def _describe(targets: frozenset[PostStatus]) -> str:
    return ", ".join(f"«{status}»" for status in sorted(targets)) or "никуда"
