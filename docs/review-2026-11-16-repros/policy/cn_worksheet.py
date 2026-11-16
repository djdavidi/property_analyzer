import sys; sys.path.insert(0,'tests')
from shapely.geometry import box, shape
from test_curve_number import fixture, feature, attach, soil, run
# All open space is lawn/good on B soil = CN 61 exactly; split into irregular strips.
for cuts in ([500037.3],[500011.7,500043.9,500071.3],[500013.37,500029.11,500063.77]):
    c=fixture(); xs=[500000]+cuts+[500100]
    c['features']['features']=[feature(f'lawn{i}',box(xs[i],4420000,xs[i+1],4420100),cn_cover='lawn',cn_condition='good') for i in range(len(xs)-1)]
    attach(c,[soil(c,shape(c['parcel']))]); w=run(c)
    print(f"strips={len(xs)-1} average_cn={w['average_cn']!r} credit_factor={w['credit_factor']} (CN61 exact -> 0.56)")
