import time
from datetime.date import fromtimestamp

# import datetime


N = 1000

record = []
t0 = time.time()
for i in range(N):
    record.append(time.time())
t1 = time.time()
print(t1)
# print(str(datetime.datetime.fromtimestamp(t1)).split()[1])

print(str(fromtimestamp(t1)).split()[1])


print(f'{(t1-t0)/N*1E9}')




#So, the basic idea, is that every message that gets decoded gets a outdict['timestamp'] = time.time()
# added to it.

#This can then be decoded with str(datetime.datetime.fromtimestamp(timestamp)).split()
