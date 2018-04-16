#!/usr/bin/env python3.6

import argparse
import boto3 
import json
import urllib
from cfnresponse import send, SUCCESS, FAILED
from command import Command
from helper import traverse_find, traverse_modify, to_path, json_serial, remove_prefix, inject_rand, return_modifier, convert
from logger import logger


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
        self.template_event()
        self.set_attributes_from_data()
        self.setup_session()
        if self.action == 'Update' and bool(self.action_obj.get('Replace',False)):
            logger.info('Replacement specified, running Create')
            self.run_commands('Create')
        else:
            self.run_commands(self.action)
        self._send_status(SUCCESS)

    def template_event(self):
        '''
        Templates out the event coming in from CFN
        Finds and replaces Random requests
        Finds and replaces Event requests 
        '''
        try:
            # This is a set of calls to helper functions which templates out the arguments
            logger.info("Raw Event: {}".format(self.raw_data))
            self.data = traverse_find(self.raw_data,self.prefix_random,self._interpolate_rand)
            self.data = traverse_find(self.data,self.prefix_event,self._template)
            for modifier in [ '!str.', '!int.' ]:
                self.data = traverse_find(self.data,modifier,self._mod)
            logger.info("Templated Event: {}".format(self.data))
        except Exception as e:
            # If user did not pass the correct properties, return failed with error.
            self.reason = "Templating Event Data Failed: {}".format(e)
            logger.error(self.reason)
            self._send_status(FAILED)
            return

    def set_attributes_from_data(self):
        '''
        Sets object attributes from event data sent from CloudFormation
        '''
        try:
            # Setup local Vars
            self.action = self.data['RequestType']
            logger.info("Action: {}".format(self.action))
            self.action_obj = self.data['ResourceProperties'].get(self.action,{})
            self.old_physical_resource_id = self.data.get('PhysicalResourceId', 'None')
            self.physical_resource_id = self.action_obj.get('PhysicalResourceId', self.old_physical_resource_id)
            logger.info("Physical Resource Id: {}".format(self.physical_resource_id))
            self.response_data = self.action_obj.get('ResponseData', {})
            logger.info("Response Data: {}".format(self.response_data))
        except Exception as e:
            # If user did not pass the correct properties, return failed with error.
            self.reason = "Missing required property: {}".format(e)
            logger.error(self.reason)
            self._send_status(FAILED)
            return

    def setup_session(self):
        '''
        Checks to see if running locally by use of test_context
        If so use profile and region from test_context
        If not let use default session
        '''
        try:
            if isinstance(self.context,test_context):
                # For testing use profile and region from test_context
                logger.debug('Using test_context')
                logger.debug("Profile: {}".format(self.context.profile))
                logger.debug("Region: {}".format(self.context.region))
                self.test = True
                self.session = boto3.session.Session(profile_name=self.context.profile,region_name=self.context.region)
            else:
                # Sets up the session in lambda context
                self.session = boto3.session.Session()
        except Exception as e:
            # Client failed
            self.reason = "Setup Session Failed: {}".format(e)
            logger.error(self.reason)
            self._send_status(FAILED)
            return

    def run_commands(self,action):
        '''
        Loops over the Commands array, init a Command obj, and run
        After each command run, it will find and replace any tempalte looking for 
        that commands output values 
        '''
        try:
            logger.info("Running Commands for {}".format(action))
            action_obj = self.data['ResourceProperties'].get(action,{})
            commands = action_obj.get('Commands', None)
            logger.info("Commands: {}".format(commands))
            # This is the main call it calls the methods, on the client, with the arguments
            count = 0
            while count < len(commands):
                # Use Command class to validate the command and run it
                command = Command(self.session,commands[count])
                response = command.run()
                # place_holder creates a key to hold the response in the response_data dict
                place_holder = "{}[{}]".format(self.action,count)
                # response_data only takes json serializable data, json_serial function switches types!
                self.response_data[place_holder] = json.loads(json.dumps(response,default=json_serial))
                logger.debug("Response: {}".format(self.response_data))
                # This set traverses the commands looking for the place_holder and replaces it with the value 
                self.current_var_fetch = place_holder
                commands = traverse_find(commands,"!{}".format(self.current_var_fetch),self._variable_fetch)
                self.response_data = traverse_find(self.response_data,"!{}".format(self.current_var_fetch),self._variable_fetch)
                logger.debug("Templated Command Set: {}".format(commands))
                count = count + 1
        except Exception as e:
            # Commands failed 
            self.reason = "Commands Failed: {}".format(e)
            logger.error(self.reason)
            self._send_status(FAILED)
            return

    def _set_buffer(self, value):
        '''
        Sets a buffer to be used later 
        '''
        self.buff = value

    def _template(self, value):
        '''
        Used in a traverse function to find and modify based on a prefix
        '''
        value = remove_prefix(value,self.prefix_event)
        traverse_modify(self.raw_data,value,self._set_buffer)
        return self.buff

    def _variable_fetch(self, value):
        '''
        Used in a traverse function to find and modify based on a prefix or modifier
        '''
        value = remove_prefix(value,"!{}.".format(self.current_var_fetch))
        mod, value = return_modifier(value)
        logger.info("Modifier: {}".format(mod))
        traverse_modify(self.response_data[self.current_var_fetch],value,self._set_buffer)
        if mod:
            return convert(self.buff,mod)
        return self.buff

    def _mod(self, value):
        mod, value = return_modifier(value)
        if mod:
            return convert(value,mod)
        return value
         
    def _interpolate_rand(self, value):
        '''
        Drops in a random number where !rand is found
        '''
        withrand = inject_rand(value,self.prefix_random)
        logger.info("WithRand returned: {}".format(withrand))
        return withrand
                
    def _send_status(self, PASS_OR_FAIL):
        '''
        Sends a Pass or Fail to CloudFormation, uses object attuibutes as response data
        '''
        if self.physical_resource_id:
            logger.info('there is phsy id')
            traverse_modify(self.response_data,to_path(remove_prefix(self.physical_resource_id,'!')),self._set_buffer)
        else: 
            self.buff = str('None')
        logger.info("Physical Resource Id After Find: {}".format(self.buff))
        #self.response_data = urllib.parse.urlencode(self.response_data).encode('ascii')
        if not self.test:
            send(
                self.raw_data,
                self.context,
                PASS_OR_FAIL,
                physical_resource_id=self.buff,
                reason=self.reason,
                response_data=self.response_data
            )
        else:
            logger.info("Context Type: {}: ".format(json.dumps(self.context)))
            logger.info("PASS/FAIL Type: {}: ".format(json.dumps(PASS_OR_FAIL)))
            logger.info("Physical Resource Id Type: {}: ".format(json.dumps(self.buff)))
            logger.info("Response Data Type: {}: ".format(json.dumps(self.response_data)))


def lambda_handler(event, context):
    boto_proxy = CfnBotoInterface(event,context)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Lambda Function to provide pass through interface to CloudFormation.')
    parser.add_argument("-r","--region", help="Region in which to run.", default='us-east-1')
    parser.add_argument("-p","--profile", help="Profile name to use when connecting to aws.", default=None)
    parser.add_argument("-m","--method_override", help="Method Type Override.", default=None, choices=[None,'Create','Update','Delete'])
    parser.add_argument("-e","--event", help="Event object passed from CFN.", default={
        'RequestType': 'Delete', 
        'ResourceProperties': { 
            'Create': {
                'PhysicalResourceId': '!Create[0].LaunchTemplate.LaunchTemplateId',
                'Commands': [
                    {
                        'Client': 'ec2',
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
                'PhysicalResourceId': '!Update[1].LaunchTemplate.LaunchTemplateId',
                'Commands': [
                    {
                        'Client': 'ec2',
                        'Method': 'describe_launch_templates',
                        'Arguments': {
                            'LaunchTemplateNames': ['TestingTemplate'],
                            'MaxResults': 1
                        }
                    }, 
                    {
                        'Client': 'ec2',
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
                        'Client': 'ec2',
                        'Method': 'modify_launch_template',
                        'Arguments': {
                            'LaunchTemplateId': '!event.PhysicalResourceId',
                            'DefaultVersion': '!Update[1].!str.LaunchTemplateVersion.VersionNumber'
                        }
                    }
                ]
            },
            'Delete': {
                'Commands': [
                    {
                        'Client': 'ec2',
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

