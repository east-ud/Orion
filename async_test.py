import asyncio
import time

SIZE = 100000

class Counter():
  def __init__(self):
    self.values = [0] * SIZE

  async def count(self):
    while True:
        await asyncio.sleep(1)
        for i in range(SIZE):
            self.values[i] += 1

  async def heartbeat(self, loop):
    t0 = time.monotonic()

    while True:
        await asyncio.sleep(1)

      # Check for consistency.
        for i in range(SIZE):
            assert self.values[i] == self.values[0], f'Value at index {i} is inconsistent'

        now = loop.time()
        print(f'All values are {self.values[0]} at +{1000*(now - t0):.0f}s')




async def main():


    counter = Counter()
    await coount()
    await hearbeat()

    #tasks = map(asyncio.create_task, [counter.count(), counter.heartbeat()])
    #await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    result1 = loop.create_task(counter.count())  # this then start subscribe_public
    result2 = loop.create_task(counter.heartbeat(loop))  # this then start subscribe_public

    loop.run_forever()

if __name__ == '__main__':
    asyncio.run(main())
