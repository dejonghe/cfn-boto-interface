# cfn_boto_interface

## Overview
This is a lambda function that aims to pass through functionality from Boto3 to CloudFormation. You're able to define in your CFN Custom Resource properties for each case, CREATE, UPDATE, and DELETE. All three of which are to set the same defined boto3 client. Each action object has two attributes method, and arguments. This also provides a way to reference other values in the lambda event.


## CFN Usage

### Runtime
* python3.6

### CloudFormation
Not shown in this example, you can use !event.OldResourceProperties.Instances[].InstanceId and the like to ease in updates and deletes. Better examples to come.

```json
  BotoInterface:
    Type: AWS::Lambda::Function
    Properties:
      Handler: lambda_function.lambda_handler
      Role: !GetAtt "IAM.Outputs.BotoInterfaceArn"
      Code:
        S3Bucket: !Ref 'CloudToolsBucket'
        S3Key: !Join [ '/', [ !Ref 'Release', 'lambda/cfn_boto_interface.zip' ] ]
      Timeout: '60'
      Runtime: python3.6
  InstanceLaunchTemplate:
    Type: Custom::InstanceLaunchTemplate
    Properties:
      ServiceToken: !GetAtt 'BotoInterface.Arn'
      Service: ec2
      Create:
        PhysicalResourceId: '!Create[0].LaunchTemplate.LaunchTemplateId'
        ResponseData:
          LaunchTemplateVersion: '!Create[0].!str.LaunchTemplate.LatestVersionNumber'
        Commands:
          - Method: create_launch_template
            Arguments:
              LaunchTemplateName: TestingTemplate
              LaunchTemplateData:
                ImageId: !Ref 'AMI'
                InstanceType: !Ref 'InstanceType'
                KeyName: !Ref 'KeyPair'
      Update:
        PhysicalResourceId: '!Update[0].LaunchTemplateVersion.LaunchTemplateId'
        ResponseData:
          LaunchTemplateVersion: '!Update[0].!str.LaunchTemplateVersion.VersionNumber'
        Commands:
          - Method: create_launch_template_version
            Arguments:
              LaunchTemplateName: TestingTemplate
              SourceVersion: 1
              LaunchTemplateData:
                ImageId: !Ref 'AMI'
                InstanceType: !Ref 'InstanceType'
                KeyName: !Ref 'KeyPair'
          - Method: modify_launch_template
            Arguments:
              LaunchTemplateId: '!event.PhysicalResourceId'
              DefaultVersion: '!Update[0].!str.LaunchTemplateVersion.VersionNumber'
      Delete:
        PhysicalResourceId: 'LaunchTemplate.LaunchTemplateId'
        Commands:
          - Method: delete_launch_template
            Arguments:
              LaunchTemplateId: '!event.PhysicalResourceId'

```



## Local Testing

```
usage: lambda_function.py [-h] [-r REGION] [-p PROFILE]
                          [-m {None,CREATE,UPDATE,DELETE}] [-e EVENT]

Lambda Function to provide pass through interface to CloudFormation.

optional arguments:
  -h, --help            show this help message and exit
  -r REGION, --region REGION
                        Region in which to run.
  -p PROFILE, --profile PROFILE
                        Profile name to use when connecting to aws.
  -m {None,CREATE,UPDATE,DELETE}, --method_override {None,CREATE,UPDATE,DELETE}
                        Method Type Override.
  -e EVENT, --event EVENT
                        Event object passed from CFN.
```



## To Do

Updates what do when require replacement
should it be a list should attribute be marked etc. 
if Action not defined do not key error just skip.
