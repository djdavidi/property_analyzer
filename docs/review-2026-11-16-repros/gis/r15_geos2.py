from shapely.geometry import box, Point, GeometryCollection
from shapely.ops import unary_union
x,y=500000,4400000
parcel=Point(x+200,y-200).buffer(60,64)
parts=[box(x+20+i*30,y-200,x+40+i*30,y-180).intersection(parcel) for i in range(10)]
print([p.geom_type+('(empty)' if p.is_empty else '') for p in parts])
roof=unary_union(parts); print('roof union:',roof.geom_type, roof.is_empty)
empty=GeometryCollection()
raw=roof.union(empty); print('raw:',raw.geom_type)
for i,p in enumerate(parts):
    try: unary_union([p]).intersection(empty)
    except Exception as e: print('part',i,p.geom_type,p.wkt[:80],'->',e)
try: raw.intersection(empty); print('ok')
except Exception as e: print('raw ∩ empty GC ->',e)
