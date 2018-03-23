from math import isnan
import time
import os
import sys

from importlib.util import find_spec
import logging

import balsam.launcher.dag as dag
from balsam.service.models import BalsamJob, END_STATES
from deephyper.evaluators import evaluate

logger = logging.getLogger(__name__)

class BalsamEvaluator(evaluate.Evaluator):

    def __init__(self, params_list, bench_module_name, num_workers=1,
                 backend='tensorflow', model_path='', data_source='', 
                 stage_in_destination=''):
        super().__init__()

        self.id_key_map = {}
        self.num_workers = num_workers
        self.params_list = params_list
        self.bench_module_name = bench_module_name
        self.bench_file = os.path.abspath(find_spec(bench_module_name).origin)
        self.backend = backend
        self.model_path = model_path
        self.data_source = data_source
        self.stage_in_destination = stage_in_destination
        
        if dag.current_job is None:
            self._init_current_balsamjob()

        logger.debug("Balsam Evaluator instantiated")
        logger.debug(f"Backend: {self.backend}")
        logger.info(f"Benchmark: {self.bench_file}")

    def stop(self):
        pass

    def _init_current_balsamjob(self):
        this = dag.add_job(name='search', workflow=self.bench_module_name,
                           wall_time_minutes=60
                          )
        this.create_working_path()
        this.update_state('JOB_FINISHED')
        dag.current_job = this
        dag.JOB_ID = this.job_id
        os.chdir(this.working_directory)
        logger.debug(f"Running in Balsam job directory: {this.working_directory}")

    def _eval_exec(self, x):
        jobname = f"task{self.counter}"
        cmd = f"{sys.executable} {self.bench_file}"
        
        param_dict = {p:v for p,v in zip(self.params_list, x)} # if 'hidden' not in p
        param_dict['model_path'] = self.model_path
        param_dict['data_source'] = self.data_source
        param_dict['stage_in_destination'] = self.stage_in_destination

        args = ' '.join(f"--{p}={v}" for p,v in param_dict.items())
        envs = f"KERAS_BACKEND={self.backend}"

        child = dag.spawn_child(
                    name = jobname,
                    direct_command = cmd,
                    application_args = args,
                    environ_vars = envs,
                    wall_time_minutes = 2,
                    num_nodes = 1, ranks_per_node = 1,
                    threads_per_rank=64,
                    serial_node_packing_count=1,
                    wait_for_parents = False
                   )
        child.create_working_path()
        child.update_state('PREPROCESSED')
        logger.debug(f"Created job {jobname}")
        logger.debug(f"Command: {cmd}")
        logger.debug(f"Args: {args}")

        self.id_key_map[child.job_id.hex] = self._encode(x)
        return child.job_id.hex

    def _read_eval_output(self, job):
        output = job.read_file_in_workdir(f'{job.name}.out')
        y = sys.float_info.max
        for line in output.split('\n'):
            if "OUTPUT:" in line.upper():
                y = float(line.split()[-1])
                break
        if isnan(y): y = sys.float_info.max
        return y

    def await_evals(self, to_read, timeout=2000, delay=5):
        keys = [self._encode(x) for x in to_read]
        job_ids = [self.pending_evals[k] for k in keys
                   if k in self.pending_evals]
        job_ids = list(set(job_ids))
        assert all(k in self.evals for k in keys if k not in self.pending_evals)

        jobs = BalsamJob.objects.filter(job_id__in=job_ids)
        num_jobs = jobs.count()
        logger.info(f"Waiting on {num_jobs} Balsam eval jobs to finish")

        num_checks = round(timeout / delay)
        for i in range(num_checks):
            num_finished = jobs.filter(state='RUN_DONE').count()
            logger.debug(f"{num_finished} out of {num_jobs} finished")
            isDone = num_finished == num_jobs
            failed = jobs.filter(state='FAILED').exists()
            if isDone: 
                break
            elif failed:
                logger.error("A balsam job failed; terminating")
                raise RuntimeError("An eval job failed")
            else:
                time.sleep(delay)

        isDone = jobs.filter(state='RUN_DONE').count() == num_jobs
        if not isDone:
            logger.error("Balsam Jobs did not finish in alloted timeout; aborting")
            raise RuntimeError(f"The jobs did not finish in {timeout} seconds")

        for job in jobs:
            y = self._read_eval_output(job)
            key = self.id_key_map[job.job_id.hex]
            self.evals[key] = y
            if key in self.pending_evals: del self.pending_evals[key]
        
        for x, key in zip(to_read, keys):
            y = self.evals[key]
            logger.info(f"x: {x} y: {y}")
            yield (x,y)
    
    def get_finished_evals(self):
        '''iter over any immediately available results'''
        pending_ids = self.pending_evals.values()
        done_jobs = BalsamJob.objects.filter(job_id__in=pending_ids)
        done_jobs = done_jobs.filter(state='RUN_DONE')
        logger.info("Checking if any pending Balsam jobs are done")

        for job in done_jobs:
            logger.info(f"Got data from {job.cute_id}")
            key = self.id_key_map[job.job_id.hex]
            x = self._decode(key)
            y = self._read_eval_output(job)
            self.evals[key] = y
            del self.pending_evals[key]
            logger.info(f"x: {x} y: {y}")
            yield (x, y)
    
    def __getstate__(self):
        d = {}
        d['evals'] = self.evals
        d['pending_evals'] = self.pending_evals
        d['id_key_map'] = self.id_key_map
        d['backend'] = self.backend
        d['num_workers'] = self.num_workers
        d['params_list'] = self.params_list
        d['bench_module_name'] = self.bench_module_name
        d['bench_file'] = self.bench_file
        return d

    def __setstate__(self, d):
        self.evals = d['evals']
        self.pending_evals = d['pending_evals']
        self.id_key_map = d['id_key_map']
        self.backend = d['backend']
        self.num_workers = d['num_workers']
        self.params_list = d['params_list']
        self.bench_module_name = d['bench_module_name']
        self.bench_file = d['bench_file']

        if dag.current_job is None:
            self._init_current_balsamjob()


        pending_ids = self.pending_evals.values()
        num_pending = BalsamJob.objects.filter(job_id__in=pending_ids).count()

        if num_pending != len(pending_ids):
            logger.error("Pickled Balsam evaluator had {len(pending_ids)} pending jobs")
            logger.error("But only {num_pending} found in Balsam DB")
            raise RuntimeError("Pending evals are missing in Balsam DB, did you delete them?")

        logger.debug("Balsam Evaluator loaded from pickle")
        logger.debug(f"Backend: {self.backend}")
        logger.info(f"Benchmark: {self.bench_file}")

        logger.info(f"Restored {len(self.evals)} finished evals")
        logger.info(f"Resuming {len(self.pending_evals)} evals")