#!/usr/bin/env python3.6

import argparse
import boto3 
import json
import logging
import urllib
from cfnresponse import send, SUCCESS, FAILED
from helper import traverse_find, traverse_modify, json_serial, remove_prefix, inject_rand, return_modifier, convert

# Setup logger
logger = logging.getLogger()
logger.setLevel(logging.INFO)
ch = logging.StreamHandler()
ch.setLevel(logging.INFO)
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
ch.setFormatter(formatter)
logger.addHandler(ch)

class test_context(dict):
    '''This is a text context object used when running function locally'''
    def __init__(self,profile,region):
        self.profile = profile
        self.region = region

# Trims prefix
def remove_prefix(text, prefix):
    return text[text.startswith(prefix) and len(prefix):]


# Core class 
class CfnBotoInterface(object):
    '''
    CfnBotoInterface is a class that takes data in from 
    a lambda event and context. This object allows for 
    a direct interface to the AWS API through the Boto3 SDK
    to CloudFormation. You're able to define in your CFN
    Custom Resource properties for each case, Create, Update,
    and Delete. All three of which are to set the same defined
    boto3 client. Each action object has two attributes
    method, and arguments. 
    '''
    reason = None
    response_data = {}
    buff = None
    prefix_event = '!event.'
    prefix_random = '!random'
    test = False


    # Initializes the object
    def __init__(self,event,context):
        logger.debug("Event Received: {}".format(event))
        self.raw_data = event
        self.context = context
        self.set_attributes_from_event(event)
        self.template_event()
        self.setup_client()
        self.run_commands()
        self.send_status(SUCCESS)

    def set_attributes_from_event(self, event):
        try:
            # Setup local Vars
            self.action = event['RequestType']
            logger.info("Action: {}".format(self.action))
            self.client_type = event['ResourceProperties']['Service']
            logger.info("Client: {}".format(self.client_type))
            self.commands = event['ResourceProperties'][self.action].get('Commands', None)
            logger.info("Commands: {}".format(self.commands))
            self.physical_resource_id = event['ResourceProperties'][self.action].get('PhysicalResourceId', 'None')
            logger.info("Physical Resource Id: {}".format(self.physical_resource_id))
            self.response_data = event['ResourceProperties'][self.action].get('ResponseData', {})
            logger.info("Response Data: {}".format(self.response_data))
        except KeyError as e:
            # If user did not pass the correct properties, return failed with error.
            self.reason = "Missing required property: {}".format(e)
            logger.info(self.reason)
            self.send_status(FAILED)
            return

    def template_event(self):
        try:
            # This is a set of calls to helper functions which templates out the arguments
            self.data = traverse_find(self.raw_data,self.prefix_random,self.interpolate_rand)
            self.data = traverse_find(self.data,self.prefix_event,self.template)
            logger.info("Templated Event: {}".format(self.data))
        except KeyError as e:
            # If user did not pass the correct properties, return failed with error.
            self.reason = "Templating Event Data Failed: {}".format(e)
            logger.info(self.reason)
            self.send_status(FAILED)
            return

    def setup_client(self):
        try:
            if isinstance(self.context,test_context):
                # For testing use profile and region from test_context
                logger.debug('Using test_context')
                logger.debug("Profile: {}".format(self.context.profile))
                logger.debug("Region: {}".format(self.context.region))
                self.test = True
                session = boto3.session.Session(profile_name=self.context.profile,region_name=self.context.region)
            else:
                # Sets up the session in lambda context
                session = boto3.session.Session()
            # Setup the client requested
            self.client = session.client(self.client_type)
        except KeyError as e:
            # Client failed
            self.reason = "Setup Client Failed: {}".format(e)
            logger.info(self.reason)
            self.send_status(FAILED)
            return

    def run_commands(self):
        try:
            logger.info('Running Commands')
            # This is the main call it calls the methods, on the client, with the arguments
            count = 0
            while count < len(self.commands):
                if count != 0:
                    logger.info('trav-find')
                    self.current_var_fetch = place_holder
                    logger.info("Var Fetch Find: {}".format(self.current_var_fetch))
                    self.commands = traverse_find(self.commands,"!{}".format(self.current_var_fetch),self.variable_fetch)
                    self.response_data = traverse_find(self.response_data,"!{}".format(self.current_var_fetch),self.variable_fetch)
                    logger.info(self.commands)
                command = self.commands[count]
                place_holder = "{}[{}]".format(self.action,count)
                method = command['Method']
                logger.info("Method: {}".format(method))
                arguments = command['Arguments']
                logger.info("Arguments: {}".format(arguments))
                response = getattr(self.client,method)(**arguments)
                self.response_data[place_holder] = json.loads(json.dumps(response,default=json_serial))
                logger.info("Response: {}".format(self.response_data))
                count = count + 1
        except KeyError as e:
            # Commands failed 
            self.reason = "Commands Failed: {}".format(e)
            logger.info(self.reason)
            self.send_status(FAILED)
            return

    def set_buffer(self, value):
        self.buff = value

    def template(self, value):
        value = remove_prefix(value,self.prefix_event)
        traverse_modify(self.raw_data,value,self.set_buffer)
        return self.buff

    def variable_fetch(self, value):
        value = remove_prefix(value,"!{}.".format(self.current_var_fetch))
        mod, value = return_modifier(value)
        logger.info("Modifier: {}".format(mod))
        traverse_modify(self.response_data[self.current_var_fetch],value,self.set_buffer)
        if mod:
            return convert(self.buff,mod)
        return self.buff

    def interpolate_rand(self, value):
        withrand = inject_rand(value,self.prefix_random)
        logger.info("WithRand returned: {}".format(withrand))
        return withrand
                
    def send_status(self, PASS_OR_FAIL):
        if self.physical_resource_id:
            traverse_modify(self.response_data,self.physical_resource_id,self.set_buffer)
        else: 
            self.buff = str('None')
        #self.response_data = urllib.parse.urlencode(self.response_data).encode('ascii')
        if not self.test:
            send(
                self.raw_data,
                self.context,
                PASS_OR_FAIL,
                physical_resource_id=self.buff,
                reason=self.reason,
                response_data=None
                #response_data=self.response_data
            )
        else:
            #logger.info("Raw Type: {}: ".format(json.dumps(self.raw_data)))
            logger.info("Context Type: {}: ".format(json.dumps(self.context)))
            logger.info("PASS/FAIL Type: {}: ".format(json.dumps(PASS_OR_FAIL)))
            logger.info("Physical Resource Id Type: {}: ".format(json.dumps(self.buff)))
            logger.info("Response Data Type: {}: ".format(json.dumps(self.response_data)))

def lambda_handler(event, context):
    boto_proxy = CfnBotoInterface(event,context)

if __name__ == "__main__":
    logger.setLevel(logging.INFO)
    parser = argparse.ArgumentParser(description='Lambda Function to provide pass through interface to CloudFormation.')
    parser.add_argument("-r","--region", help="Region in which to run.", default='us-east-1')
    parser.add_argument("-p","--profile", help="Profile name to use when connecting to aws.", default=None)
    parser.add_argument("-m","--method_override", help="Method Type Override.", default=None, choices=[None,'Create','Update','Delete'])
    parser.add_argument("-e","--event", help="Event object passed from CFN.", default={
        'RequestType': 'Delete', 
        'ResourceProperties': { 
            'Service': 'ec2',
            'Create': {
                'PhysicalResourceId': '!Create[0].LaunchTemplate.LaunchTemplateId',
                'Commands': [
                    {
                        'Method': 'create_launch_template',
                        'Arguments': {
                            'LaunchTemplateName': 'TestingTemplate',
                            'LaunchTemplateData': {
                                'ImageId': 'ami-cb17d8b6',
                                'InstanceType': 't2.large',
                                'KeyName': 'common-us-east-1'
                            }
                        }
                    }
                ]
            },
            'Update': {
                'PhysicalResourceId': '!Update[0].LaunchTemplate.LaunchTemplateId',
                'Commands': [
                    {
                        'Method': 'create_launch_template_version',
                        'Arguments': {
                            'LaunchTemplateName': 'TestingTemplate',
                            'SourceVersion': '1',
                            'LaunchTemplateData': {
                                'InstanceType': 't2.medium'
                            }
                        }
                    },
                    {
                        'Method': 'modify_launch_template',
                        'Arguments': {
                            'LaunchTemplateName': 'TestingTemplate',
                            'DefaultVersion': '!Update[0].!str.LaunchTemplateVersion.VersionNumber'
                        }
                    }
                ]
            },
            'Delete': {
                'Commands': [
                    {
                        'Method': 'delete_launch_template',
                        'Arguments': {
                            'LaunchTemplateName': 'TestingTemplate',
                        }
                    }
                ]
            },
            'OtherEvent': [
                 {'Method': '!event.OldResourceProperties.Value'}
            ],
            'OtherRand': [ 
                 {'!random.OldResourceProperties.Value-!random.something'}
            ]
        }
    })
    args = parser.parse_args()

    if args.method_override:
        args.event['RequestType'] = args.method_override
    
    context = test_context(args.profile,args.region)
    lambda_handler(args.event, context)

