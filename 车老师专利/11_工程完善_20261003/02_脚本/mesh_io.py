from pathlib import Path
import json
import numpy as np
ROOT=Path('车老师专利/11_工程完善_20261003/06_仿真/FEM')
def read_mesh(path):
    lines=Path(path).read_text().splitlines();nodes={};tri=[];tet=[];i=0
    while i<len(lines):
        if lines[i]=='$Nodes':
            count=int(lines[i+1]);i+=2
            for line in lines[i:i+count]:
                v=line.split();nodes[int(v[0])]=np.array([float(n) for n in v[1:4]])
            i+=count
        elif lines[i]=='$Elements':
            count=int(lines[i+1]);i+=2
            for line in lines[i:i+count]:
                v=[int(n) for n in line.split()];eid,etype,nt=v[:3];tags=v[3:3+nt];ids=v[3+nt:]
                if etype in (2,9):tri.append((eid,tags[-1],ids))
                if etype in (4,11):tet.append((eid,ids))
            i+=count
        else:i+=1
    return nodes,tri,tet

def samples(name):
    nodes,tri,tet=read_mesh(ROOT/(name+'.msh'));samples={}
    for _,surface,ids in tri:
        if len(samples.setdefault(surface,[]))<8:
            samples[surface].append(np.mean([nodes[n] for n in ids[:3]],axis=0).tolist())
    (ROOT/(name+'_samples.json')).write_text(json.dumps(samples),encoding='utf-8')
    vols=[]
    for _,ids in tet:
        a,b,c,d=[nodes[n] for n in ids[:4]]
        vols.append(np.linalg.det(np.stack([b-a,c-a,d-a],axis=1))/6)
    print(json.dumps({'nodes':len(nodes),'tetra':len(tet),'surface_triangles':len(tri),'min_signed_volume_mm3':float(min(vols)),'negative_linear_tetra':int(sum(v<=0 for v in vols)),'mesh_volume_mm3':float(sum(vols))}))

def deck(name,pressure=7):
    nodes,tri,tet=read_mesh(ROOT/(name+'.msh'))
    selected=json.loads((ROOT/(name+'_wet_surfaces.json')).read_text(encoding='utf-8'))['wet_surfaces']
    selected=set(selected)
    boundary={tuple(sorted(ids[:3])):surf for _,surf,ids in tri}
    sides=[(0,1,2),(0,3,1),(1,3,2),(2,3,0)]
    loads=[];fixed=[];out=['*HEADING','CAD block development FEA; mm,N,MPa; all nominal hydraulic cavities pressurised; mounted bottom fixed','*NODE,NSET=NALL']
    for n,xyz in nodes.items():
        out.append(str(n)+','+','.join(f'{v:.12g}' for v in xyz))
        if abs(xyz[2])<1e-7:fixed.append(n)
    out.append('*ELEMENT,TYPE=C3D10,ELSET=EALL')
    for eid,ids in tet:
        a,b,c,d=ids[:4]
        corners=[a,b,c,d];mids=[]
        for u,v in ((a,b),(b,c),(a,c),(a,d),(b,d),(c,d)):
            mid=(nodes[u]+nodes[v])/2
            chosen=min(ids[4:],key=lambda n:np.linalg.norm(nodes[n]-mid))
            if np.linalg.norm(nodes[chosen]-mid)>1e-6:raise ValueError('Unexpected curved midside coordinates')
            mids.append(chosen)
        if len(set(mids))!=6:raise ValueError('Invalid edge ordering')
        out.append(str(eid)+','+','.join(map(str,corners+mids)))
        for face,loc in enumerate(sides,1):
            if boundary.get(tuple(sorted(corners[j] for j in loc))) in selected:loads.append((eid,face))
    out+=['*NSET,NSET=BASE']
    for i in range(0,len(fixed),16):out.append(','.join(map(str,fixed[i:i+16])))
    out+=['*MATERIAL,NAME=STEEL45','*ELASTIC','206000,0.3','*SOLID SECTION,ELSET=EALL,MATERIAL=STEEL45','*BOUNDARY','BASE,1,3','*STEP','*STATIC','*DLOAD']
    out.extend(f'{eid},P{face},{pressure}' for eid,face in loads)
    out+=['*NODE FILE','U,RF','*EL FILE','S','*NODE PRINT,NSET=BASE,TOTALS=ONLY','RF','*END STEP']
    (ROOT/(name+'.inp')).write_text('\n'.join(out)+'\n',encoding='ascii')
    result={'mesh':name,'nodes':len(nodes),'tetra':len(tet),'loaded_faces':len(loads),'fixed_nodes':len(fixed),'pressure_MPa':pressure,'boundary':'all bottom nodes fixed XYZ, local block test only; bolt/contact/valve preload excluded','geometry':'straight quadratic elements on CAD-derived faceted boundary'}
    (ROOT/(name+'_input_summary.json')).write_text(json.dumps(result,indent=2),encoding='utf-8');print(json.dumps(result))
if __name__=='__main__':
    import sys
    if sys.argv[1]=='samples':samples(sys.argv[2])
    elif sys.argv[1]=='deck':deck(sys.argv[2],float(sys.argv[3]) if len(sys.argv)>3 else 7)
