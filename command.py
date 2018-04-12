class Command(object):
    '''
    Command validates each command object in the Commands array. 
    Command builds the session and client and runs the boto3 command.
    '''

    arguments = {}
    method = None

    def __init__(self,session,cmd):
        self._validate(cmd)
        self.session = session
        self.arguments = cmd['Arguments']
        self.client = cmd['Client']
        self.method = cmd['Method']
        self.client = self.session.client(cmd['Client'])

    def _validate(self,cmd_obj):
        assert type(cmd_obj) is dict, "Command Object must be of type dict"
        assert 'Client' in cmd_obj, "Command Object must have 'Client' key"
        assert type(cmd_obj['Client']) is str, "Client must be of type str"
        assert 'Method' in cmd_obj, "Command Object must have 'Method' key"
        assert type(cmd_obj['Method']) is str, "Method must be of type str"
        assert 'Arguments' in cmd_obj, "Command Object must have 'Arguments' key"
        assert type(cmd_obj['Arguments']) is dict, "Arguments must be of type dict"


    def run(self):
        response = getattr(self.client,self.method)(**self.arguments)
        return response

