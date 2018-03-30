# cfn_boto_interface

## Overview
This is a lambda function that aims to pass through functionality from Boto3 to CloudFormation. You're able to define in your CFN Custom Resource properties for each case, CREATE, UPDATE, and DELETE. All three of which are to set the same defined boto3 client. Each action object has two attributes method, and arguments. This also provides a way to reference other values in the lambda event.


## CFN Usage
Not shown in this example, you can use !event.OldResourceProperties.Instances[].InstanceId and the like to ease in updates and deletes. Better examples to come.

```json
    "BotoInterface": {
      "Type": "AWS::Lambda::Function",
      "Properties": {
        "Handler": "lambda_fuction.lambda_handler",
        "Role": { "Ref" : "LambdaRoleArn" },
        "Code": {
          "S3Bucket" : { "Ref": "CloudToolsBucket" },
          "S3Key" : { "Fn::Join": [ "/", [ { "Ref": "Release" }, "lambda/boto_interface.zip" ] ] }
        },
        "Timeout" : "60",
        "Runtime": "python2.7"
      }
    },
    "S3BucketFromBoto": {
      "Condition": "LambdaAvailable",
      "Type": "Custom::NumberAzs",
      "Properties": {
        "ServiceToken": { "Ref": "BotoInterface" }
        "Service": "s3",
        "CREATE": {
          "Method": "create_bucket",
          "Arguments": {
            "Bucket": "cfnbotointerface"
          }
        },
        "DELETE": {
          "Method": "delete_bucket",
          "Arguments": {
            "Bucket": "cfnbotointerface"
          }
        },
        "UPDATE": {
          "Method": "update_bucket"
        }
      }
    }

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



