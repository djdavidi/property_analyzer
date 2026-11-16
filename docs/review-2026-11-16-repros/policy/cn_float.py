import random, math
from stormwater.rules import open_space_factor
random.seed(1)
hits=0; ex=None
for trial in range(20000):
    areas=[random.uniform(1,5000) for _ in range(random.randint(2,6))]
    cn=61
    avg=sum(a*cn for a in areas)/sum(areas)   # same formula as curve_number.py:150-152
    if math.ceil(avg)!=cn:
        hits+=1; ex=ex or (areas,avg,open_space_factor(avg),open_space_factor(cn))
print('trials with uniform CN61 whose area-weighted average ceil()s to 62:',hits,'of 20000')
print('example:',ex)
