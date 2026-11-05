"""Drain in-flight requests for database restore in the supported single-worker deployment."""
import asyncio

class OperationGate:
    def __init__(self,app):
        self.app=app
        self.condition=asyncio.Condition()
        self.active=0
        self.exclusive=False

    async def __call__(self,scope,receive,send):
        if scope['type']!='http': return await self.app(scope,receive,send)
        exclusive=scope['path']=='/api/v1/settings-center/restore' and scope['method']=='POST'
        async with self.condition:
            await self.condition.wait_for(lambda:not self.exclusive)
            if exclusive:
                self.exclusive=True
                try:
                    await self.condition.wait_for(lambda:self.active==0)
                except BaseException:
                    self.exclusive=False
                    self.condition.notify_all()
                    raise
            else: self.active+=1
        try: await self.app(scope,receive,send)
        finally:
            async with self.condition:
                if exclusive:self.exclusive=False
                else:self.active-=1
                self.condition.notify_all()
