# cfn_boto_interface

## Overview
This is a lambda function that aims to pass through functionality from Boto3 to CloudFormation through a descriptive object. 

## Lambda Zip
You can download a prebuilt lambda zip from the release section of this github repository, or build your own.

### Building the Lambda Zip
You probably have your own way of building lambda zips but this should work given you're using bash that has pip and zip commands.
```bash
mkdir temp
cp -r ./* temp/
cd temp
pip install -t . -r requirements.txt
zip -r ../cfn_boto_interface.zip ./* 
cd ..
rm -rf temp
```

*Upload this zip file to a S3 bucket*

## CFN Usage

### Runtime
* python3.6

### CloudFormation: Lambda Resource
Create the lambda resource like so:
```yaml
  BotoInterface:
    Type: AWS::Lambda::Function
    Properties:
      Handler: lambda_function.lambda_handler
      Role: !GetAtt 'BotoInterfaceRole.Arn' # IAM Role Arn with sufficient privledges 
      Code:
        S3Bucket: !Ref 'CloudToolsBucket' # Bucket containing zip of packaged code
        S3Key: !Join [ '/', [ !Ref 'Release', 'lambda/cfn_boto_interface.zip' ] ] # S3 Object key 
      Timeout: '60' # Set appropriate timeout for your function
      Runtime: python3.6 # Python3.6 Required
```

Once you have the lambda function you can call it with a custom resource, examples below.

### Custom Resource Properties

#### Top level properties
* ServiceToken: (Required) - Arn of the Lambda Resource 
* Create: ActionObject, described below
* Update: ActionObject, described below
* Delete: ActionObject, described below
 
#### ActionObject
* PhysicalResourceId: Physical Id of this resource to return to CloudFormation for this action. Can use *Lookups*
* ResponseData: Dict of key,value pairs to return to CloudFormation for this resource for this action, for use in GetAtt. Can use *Lookups*
* Commands: Array of CommandObjects 
* Replace: (Update Only) - Bool, will re run create, if a different PhysicalId is returned CloudFormation will send a Delete when Cleaning Up

#### CommandObjects
* Client: (Required) - Boto3 client name to use when creating a client example: 'ec2', or 'secretsmanager'
* Method: (Required) - Method to call on the Boto3 client
* Arguments: Dict of key,value pairs to pass to the method as keyword arguments.

#### Lookups
Lookups are denoted with a `!` prefix. The lookups traverse dict objects by use of `.` notation
* `!event.`: Looks up a value in the event passed to the lambda from CloudFormation
* `!Create[].`: (Create ActionObject Only) - Looks up a value from the return of the command at that index ran in the Create ActionObject
* `!Update[].`: (Update ActionObject Only) - Looks up a value from the return of the command at that index ran in the Update ActionObject
* `!Delete[].`: (Delete ActionObject Only) - Looks up a value from the return of the command at that index ran in the Delete ActionObject

##### Modifiers
If a lookup returns a value in a type that you need to cast you can use the modifiers after the lookup notation.
* `!int.`: Cast lookup to int
* `!str.`: Cast lookup to str

#### Interpolation
* `!random`: Interpolates a random 4 AlphaNumeric string


```yaml
  InstanceLaunchTemplate:
    Type: Custom::InstanceLaunchTemplate
    Properties:
      ServiceToken: !GetAtt 'BotoInterface.Arn'
      # When a create event type is send to the lambda use this object
      Create:
        # Sets the return PhysicalResourceId, used in Ref. Looks up the response of the first command 
        PhysicalResourceId: '!Create[0].LaunchTemplate.LaunchTemplateId'
        # Sets the response data used with GetAtt's 
        ResponseData:
          LaunchTemplateVersion: '!Create[0].!str.LaunchTemplate.LatestVersionNumber'
        # Array of commands to run.
        Commands:
            # The method to call on the boto client
          - Client: ec2
            Method: create_launch_template
            # The arguments that need to be passed to that method.
            Arguments:
              LaunchTemplateName: TestingTemplate1
              LaunchTemplateData:
                ImageId: !Ref 'AMI'
                InstanceType: !Ref 'InstanceType'
                KeyName: !Ref 'KeyPair'
      Update:
        PhysicalResourceId: '!Update[1].LaunchTemplateVersion.LaunchTemplateId'
        ResponseData:
          LaunchTemplateVersion: '!Update[1].!str.LaunchTemplateVersion.VersionNumber'
          SourceVersion: '!Update[0].!str.LaunchTemplates[].DefaultVersionNumber'
        Commands:
          - Client: ec2
            Method: describe_launch_templates
            Arguments:
              LaunchTemplateIds:
                - '!event.PhysicalResourceId'
          - Client: ec2
            Method: create_launch_template_version
            Arguments:
              LaunchTemplateId: '!event.PhysicalResourceId'
              SourceVersion: '!Update[0].!str.LaunchTemplates[].DefaultVersionNumber'
              LaunchTemplateData:
                ImageId: !Ref 'AMI'
                InstanceType: !Ref 'InstanceType'
                KeyName: !Ref 'KeyPair'
          - Client: ec2
            Method: modify_launch_template
            Arguments:
              LaunchTemplateId: '!event.PhysicalResourceId'
              DefaultVersion: '!Update[1].!str.LaunchTemplateVersion.VersionNumber'
      Delete:
        PhysicalResourceId: 'LaunchTemplate.LaunchTemplateId'
        Commands:
          - Client: ec2
            Method: delete_launch_template
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



