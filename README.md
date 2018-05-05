## Step 1:
### Execute CreateBaseVpc.json
 1. Create a VPC with internet gateway
 2. Create public subnets in each availability zone
 3. Create a NAT gateway and VPC endpoints (S3 endpoint and DynamoDB endpoint) in each subnet
 4. Create a public route table with 0.0.0.0/0 points to internet gateway
 5. Create an external route tables in each subnet, the default route set to the NAT gateway in same subnet, add route to VPC endpoints in same subnet
 6. Create an internal route tables in each subnet, add route to VPC endpoints in same subnet
## Step 2:
### Execute SubnetAuto.json
 1. Create subnets based on requirement, for example::
```
      f5:10:1a:p,f5:10:1b:p
```
> This command will create 2 subnets, the function of the subnet is "f5", the servers that will be hosted in each subnet is "10", the first subnet will be created in availability zone "1a", the second subnet will be created in availability zone "1b". The route table will be associated to each subnet is "p", which means public route table.
       
            
> The route table type can be: p, e and i. In order to avoid lambda function timeout, the recommended maximum subnets can be created is 14.
```
f5:10:1a:p,f5:10:1b:p,web01:20:1a:e,web01:20:1b:e,app01:30:1a:e,app01:30:1b:e,db01:15:1a:i,db01:15:1b:i,web02:20:1a:e,web02:20:1b:e,app02:30:1a:e,app02:30:1b:e,db02:15:1a:i,db02:15:1b:i
```
This command will create 14 subnets

 2 .Associate appropriate route table to each subnet
## Step 3:
 If you want to create more subnets, just execute SubnetAuto.json as any times as you want.
