import os
import logging
from . import pwstaging


def get_stage_in_cmd(file, jumphost = None):
    if jumphost:
        # Prefix rsync command with ssh to setup multiplex.
        # Executing two commands separated by ; with command substitution
        # does not normally work in bash, but works for
        # the special case we use subprocess.run(cmd, shell=True)
        # in the wrapper.
        cmd = "ssh -o \"ControlPath ~/.ssh/%C\" -J {jumphost} {hostname} exit; rsync -avzq  -e 'ssh -J {jumphost}' {hostname}:{permanent_filepath} {worker_filepath}".format(
            jumphost = jumphost,
            hostname = file.netloc,
            permanent_filepath = file.path,
            worker_filepath = file.local_path
        )
    else:    
        cmd = "rsync -avzq {hostname}:{permanent_filepath} {worker_filepath}".format(
            hostname = file.netloc,
            permanent_filepath = file.path,
            worker_filepath = file.local_path
        )
    return cmd

def get_stage_out_cmd(file, jumphost = None):
    if jumphost:
        # Prefix rsync command with ssh to setup multiplex.
        # Executing two commands separated by ; with command substitution
        # does not normally work in bash, but works for
        # the special case we use subprocess.run(cmd, shell=True)
        # in the wrapper.
        cmd = "ssh -o \"ControlPath ~/.ssh/%C\" -J {jumphost} {hostname} exit; rsync -avzq -e 'ssh -J {jumphost}' --rsync-path=\"mkdir -p {root_path} && rsync\" {worker_filepath} {hostname}:{permanent_filepath}".format(
            jumphost = jumphost,
            hostname = file.netloc,
            permanent_filepath = file.path,
            worker_filepath = file.local_path,
            root_path = os.path.dirname(file.path)
        )
    else:
        cmd = "rsync -avzq --rsync-path=\"mkdir -p {root_path} && rsync\" {worker_filepath} {hostname}:{permanent_filepath}".format(
            hostname = file.netloc,
            permanent_filepath = file.path,
            worker_filepath = file.local_path,
            root_path = os.path.dirname(file.path)
        )

    return cmd

class PWRSyncStaging(pwstaging.PWStaging):
    """
    This is a modification of the official staging provider 
    https://parsl.readthedocs.io/en/latest/stubs/parsl.data_provider.rsync.RSyncStaging.html
    with three changes:
        1. Add -avzq option to rsync
        2. Make parent directory of file.path if it does not exist
        3. Allow the user the specify the private IP of the head node.

    This staging provider will execute rsync on worker nodes
    to stage in files from a remote location.
    Worker nodes must be able to authenticate to the rsync server
    without interactive authentication - for example, worker
    initialization could include an appropriate SSH key configuration.
    The submit side will need to run an rsync-compatible server (for example,
    an ssh server with the rsync binary installed)

    It is assumed that the SSH tunnels/config from the PW platform
    are already in place so that worker nodes can simply
         ssh -J <head_node_private_ip> usercontainer
    in order to reach the PW user's IDE. All rsync commands here are
    prefixed with ssh -J and this approach works even if the Parsl
    app is for some reason running on the head node itself instead
    of the worker nodes.

    The default value is set to None which will disable the use of
    ssh -J and assume that the node that is running the rsync command
    has direct ssh access to the host the workflow configuration is
    pointing to.
    """

    def __init__(self, executor_label, head_node_private_ip = None, logging_level = logging.INFO):
        self.executor_label = executor_label
        self.logging_level = logging_level
        super().__init__('file', executor_label, logging_level = logging_level)
        self.head_node_private_ip = head_node_private_ip

    def replace_task(self, dm, executor, file, f):
        working_dir = dm.dfk.executors[executor].working_dir
        cmd = get_stage_in_cmd(file, jumphost = self.head_node_private_ip)
        cmd_id = self._get_cmd_id(cmd)  
        return pwstaging.in_task_stage_in_cmd_wrapper(f, file, working_dir, cmd, cmd_id, self.logger.getEffectiveLevel())
    
    def replace_task_stage_out(self, dm, executor, file, f):
        working_dir = dm.dfk.executors[executor].working_dir
        cmd = get_stage_out_cmd(file, jumphost = self.head_node_private_ip)
        cmd_id = self._get_cmd_id(cmd)  
        cmd_id = self._get_cmd_id(cmd)  
        return pwstaging.in_task_stage_out_cmd_wrapper(f, file, working_dir, cmd, cmd_id, self.logger.getEffectiveLevel())
