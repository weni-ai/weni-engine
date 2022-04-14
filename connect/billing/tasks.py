@app_task()
def retry_billing_tasks():
    task_failed = SyncManagerTask.objects.filter(status=False, retried=False)
    
    for task in task_failed:
        status = False
        task.retried = True
        task.save()
        if task.task_type == 'count_contacts':
            # todo: call count task
            
            status = True
            pass
        elif task.task_type == 'sync_contacts':
            #todo: call sync task
            status = sync_contacts()
            pass
        