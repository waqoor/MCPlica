from abc import ABC, abstractmethod


class AsyncClient(ABC):
    @abstractmethod
    async def health(self) -> bool: ...

    async def close(self) -> None:
        return None
