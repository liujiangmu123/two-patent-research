import FreeCAD as App
job=App._che_job
_result_={k:v for k,v in job.items() if k not in ('summary','parts','shapes','nets')}
