from __future__ import annotations

from typing import Callable, Iterable, List, Optional, Sequence

from .pipeline import NormalizationPipeline, NormalizationStage

StageFactory = Callable[[], NormalizationStage]


class StageRegistry:
    def __init__(self) -> None:
        self._entries: List[tuple[str, StageFactory]] = []
        self._version: int = 0

    def register(
        self,
        factory: StageFactory,
        *,
        name: Optional[str] = None,
        before: Optional[str] = None,
        after: Optional[str] = None,
        replace: bool = False,
    ) -> None:
        key = name or factory.__name__
        if replace:
            self._entries = [(k, f) for (k, f) in self._entries if k != key]
        if key in {k for (k, _) in self._entries} and not replace:
            raise ValueError(f"Stage '{key}' уже зарегистрирован")

        entry = (key, factory)
        if before:
            self._insert_before(entry, before)
        elif after:
            self._insert_after(entry, after)
        else:
            self._entries.append(entry)
        self._version += 1

    def _insert_before(self, entry: tuple[str, StageFactory], target: str) -> None:
        for idx, (key, _) in enumerate(self._entries):
            if key == target:
                self._entries.insert(idx, entry)
                return
        self._entries.append(entry)

    def _insert_after(self, entry: tuple[str, StageFactory], target: str) -> None:
        for idx, (key, _) in enumerate(self._entries):
            if key == target:
                self._entries.insert(idx + 1, entry)
                return
        self._entries.append(entry)

    def create_pipeline(self, *, overrides: Optional[Iterable[NormalizationStage]] = None) -> NormalizationPipeline:
        if overrides is not None:
            return NormalizationPipeline(stages=list(overrides))
        stages = [factory() for _, factory in self._entries]
        return NormalizationPipeline(stages)

    def list_stage_names(self) -> Sequence[str]:
        return [name for name, _ in self._entries]

    @property
    def version(self) -> int:
        return self._version


default_registry = StageRegistry()


def register_stage(
    factory: StageFactory,
    *,
    name: Optional[str] = None,
    before: Optional[str] = None,
    after: Optional[str] = None,
    replace: bool = False,
) -> None:
    default_registry.register(factory, name=name, before=before, after=after, replace=replace)
