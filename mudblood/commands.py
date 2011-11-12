class CommandObject:
    def pass_command(self, cmd):
        if hasattr(self, "cmd_" + cmd[0]):
            ret = getattr(self, "cmd_" + cmd[0])(*(cmd[1:]))
            if not ret:
                return True
            return ret
        else:
            return False

class CommandChain:
    def __init__(self):
        self.chain = []

    def run_command(self, cmd):
        for o in self.chain:
            ret = o.pass_command(cmd)
            if ret:
                return ret
        return False

