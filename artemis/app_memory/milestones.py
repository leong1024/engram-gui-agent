from dataclasses import dataclass

from artemis.utils.plan_grammar import PlanSnapshot


@dataclass(frozen=True, slots=True)
class Milestone:
    """A top-level plan milestone. `key` is its `subgoal_hash`, the key steps carry."""

    key: str
    text: str
    details: tuple[str, ...] = ()

    @property
    def query(self) -> str:
        return "\n".join((self.text, *self.details))


def plan_milestones(plan: PlanSnapshot) -> list[Milestone]:
    return [
        Milestone(
            item.key, item.text.strip(), tuple(c.text.strip() for c in plan.children_of(item))
        )
        for item in plan.top_level
    ]
