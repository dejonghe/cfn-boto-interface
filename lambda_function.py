#!/usr/bin/env python2.7

import argparse
import boto3 
import json
import logging
from cfnresponse import send, SUCCESS, FAILED
from helper import traverse_find, traverse_modify

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
    response_data = None
    buff = None
    prefix = '!event.'

    # Initializes the object
    def __init__(self,event,context):
        logger.debug("Event Received: {}".format(event))
        self.raw_data = event
        self.context = context
        try:
            # Setup local Vars
            action = event['RequestType']
            logger.info("Action: {}".format(action))
            client_type = event['ResourceProperties']['Service']
            logger.info("Client: {}".format(client_type))
            method = event['ResourceProperties'][action]['Method']
            logger.info("Method: {}".format(method))
            arguments = event['ResourceProperties'][action]['Arguments']
            logger.info("Arguments: {}".format(arguments))
        except KeyError as e:
            # If user did not pass the correct properties, return failed with error.
            self.reason = "Missing required property: {}".format(e)
            if self.context:
                self.send_status(FAILED)
            else:
                logger.info(self.reason)
            return
        try:
            # This is a call to a helper function which templates out the arguments
            self.data = traverse_find(self.raw_data,self.prefix,self.template)
            logger.debug("Templated Event: {}".format(self.data))
            if isinstance(context,test_context):
                # For testing use profile and region from test_context
                logger.debug('Using test_context')
                logger.debug("Profile: {}".format(context.profile))
                logger.debug("Region: {}".format(context.region))
                session = boto3.session.Session(profile_name=context.profile,region_name=context.region)
            else:
                # Sets up the session in lambda context
                session = boto3.session.Session()
            # Setup the client requested
            self.client = session.client(client_type)
            logger.info('Running...')
            # This is the main call it calls the method, on the client, with the arguments
            self.response_data = json.dumps(getattr(self.client,method)(**arguments))
            logger.info("Response: {}".format(self.response_data))
            if not isinstance(context,test_context):
                # Success! 
                self.send_status(SUCCESS)
            else:
                logger.info(self.response_data)
        except Exception as e:
            self.reason = "Failed: {}".format(e)
            if not isinstance(context,test_context):
                self.send_status(FAILED)
            else:
                logger.info(self.reason)
            return


    def set_buffer(self, value):
        self.buff = value

    def template(self, value):
        value = remove_prefix(value,self.prefix)
        traverse_modify(self.raw_data,value,self.set_buffer)
        return self.buff
                
    def send_status(self, PASS_OR_FAIL):
        send(
            self.raw_data,
            self.context,
            PASS_OR_FAIL,
            reason=self.reason,
            response_data=self.response_data
        )


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
            'Service': 's3',
            'CREATE': {
                'Method': 'create_bucket',
                'Arguments': {
                    'Bucket': 'cfnbotointerface'
                }
            },
            'DELETE': {
                'Method': 'delete_bucket',
                'Arguments': {
                    'Bucket': 'cfnbotointerface'
                }
            },
            'Other': '!event.OldResourceProperties.Value'
        },
        'OldResourceProperties': {
            'Value':'Thing'
        }
    })
    args = parser.parse_args()

    if args.method_override:
        args.event['RequestType'] = args.method_override
    
    context = test_context(args.profile,args.region)
    lambda_handler(args.event, context)

