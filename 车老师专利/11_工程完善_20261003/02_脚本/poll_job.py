import FreeCAD as App
job = getattr(App, '_che_job', {})
_result_ = {k: v for k, v in job.items() if k not in ('parts', 'shapes', 'nets')}
