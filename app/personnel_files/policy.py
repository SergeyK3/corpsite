"""Pure operation policy. Authority and scope facts must come from the server."""
from dataclasses import dataclass

KINDS = frozenset({'photo', 'certificate', 'diploma', 'identity', 'name_change'})
STATUSES = frozenset({'pending', 'returned', 'approved', 'superseded', 'revoked', 'archived'})


@dataclass(frozen=True)
class Access:
    owner: bool = False
    reviewer: bool = False
    technical: bool = False
    leader: bool = False

    def visible(self, status: str) -> bool:
        return self.owner or self.reviewer or self.technical or (self.leader and status == 'approved')

    def export(self, kind: str, status: str) -> bool:
        return self.visible(status) and (self.reviewer or (self.owner and kind in {'certificate', 'diploma'} and status == 'approved'))

    @property
    def upload(self) -> bool:
        return self.owner or self.reviewer


def transition(status: str, action: str, reason: str) -> str:
    allowed = {
        ('pending', 'approve'): 'approved',
        ('pending', 'return'): 'returned',
        ('approved', 'revoke'): 'revoked',
        ('returned', 'archive'): 'archived',
        ('superseded', 'archive'): 'archived',
        ('revoked', 'archive'): 'archived',
    }
    if (status, action) not in allowed:
        raise ValueError('Действие недоступно для текущего состояния файла.')
    if action != 'approve' and not reason.strip():
        raise ValueError('Укажите причину решения.')
    return allowed[status, action]
