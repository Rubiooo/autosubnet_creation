## This is a set of CloudFormation template and lambda functions. The initial idea comes from https://github.com/ACloudGuru/AdvancedCloudFormation/tree/master/206-LambdaCustomEnhancements. I made some modifications:
1. Do not use DynamoDB
2. Add new feature to allow create different subnets CIDR(the number of subnet and the route table of subnet can be changed) based on input parameter

## Step 1:
### Execute CreateBaseVpc.json
 1. Create a VPC with internet gateway
 2. Create public subnets in each availability zone
 3. Create a NAT gateway and VPC endpoints (S3 endpoint and DynamoDB endpoint) in each subnet
 4. Create a public route table with default route sets to internet gateway
 5. Create an external route table in each subnet, the default route sets to the NAT gateway in the same subnet, add route to VPC endpoints in the same subnet
 6. Create an internal route table in each subnet, add route to VPC endpoints in the same subnet
## Step 2:
### Execute SubnetAuto.json
 1. Create subnets based on requirement, for example::
                       
 **SubnetParameters:** 
  ```
 f5:10:1a:p,f5:10:1b:p
  ```
> This parameter will create 2 subnets, the function of the subnet is "f5", required available network addresses in each subnet is "10", the first subnet will be created in availability zone "1a", the second subnet will be created in availability zone "1b". The route table will be associated to each subnet is "p", which means public route table.
      

> The route table type can be: p, e and i. You need to pay attention to the total number of subnets that can be created to avoid lambda function time out. For example, if you use 128MB memory, the total number should be no more than 14.  If you set the memory size to 1024MB, then you can create 30 subnets at one time.
 
**SubnetParameters:** 
```
f5:10:1a:p,f5:10:1b:p,web01:20:1a:e,web01:20:1b:e,app01:30:1a:e,app01:30:1b:e,db01:15:1a:i,db01:15:1b:i,web02:20:1a:e,web02:20:1b:e,app02:30:1a:e,app02:30:1b:e,db02:15:1a:i,db02:15:1b:i
```
This parameter will create 14 subnets

 2 .Associate appropriate route table to each subnet
## Step 3:
 If you want to create more subnets, just execute SubnetAuto.json as many times as you want.


## Installation:
Create an S3 bucket in the same region that you want to create VPC, put 3 zip files in the bucket.
The bucket name is the parameter of **LambdaBucket** in CreateBaseVpc.json
