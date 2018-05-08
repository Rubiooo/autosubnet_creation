import boto3
import network_subtract
import vpc_subnet
import ipam
import copy
import netaddr
import json
import requests
import random
import string
import time


debug = ''


def SubnetParameters(input):
    # input example:   tag:capacity:AZ(1a, 1b):public(p),external(e) or internal(i),
    SubnetSets = {"subnet": []}
    detail = {}
    SubnetList = input.split(',')

    for i in range(0, len(SubnetList)):
        tmp = SubnetList[i].split(':')
        print len(tmp)
        print tmp
        if len(tmp) != 4:
            print ("Parameter input error! exit from SubnetParameters()")
            return
        detail['fuc'] = tmp[0]
        detail['capacity'] = tmp[1]
        detail['az'] = tmp[2]
        detail['route'] = tmp[3]
        d = copy.deepcopy(detail)
        SubnetSets['subnet'].append(d)
    print ("end SubnetParameters")
    return SubnetSets

#
# a = SubnetParameters('web1:50:1a:p,web2:50:1a:p')
# print a


def GetAz(az):
    client = boto3.client('ec2')
    response = client.describe_availability_zones()
    for item in response['AvailabilityZones']:
        if az in item['ZoneName']:
            return item['ZoneName']
            break
# Function Test:
# print GetAz('1b')


def GetRouteTable(route_table_type, vpc_id):
    result = {}
    zonenames = []
    client = boto3.client('ec2')
    zones = client.describe_availability_zones()
    for az in zones['AvailabilityZones']:
        zonenames.append(az['ZoneName'])
    if route_table_type == 'p':
        response = client.describe_route_tables(Filters=[{'Name': 'tag:VPC', 'Values': [
                                                vpc_id]}, {'Name': 'tag:Name', 'Values': ['PublicRouteTable']}])
        return response['RouteTables'][0]['RouteTableId']

    elif route_table_type == 'e':
        for zonename in zonenames:
            response = client.describe_route_tables(Filters=[{'Name': 'tag:VPC', 'Values': [vpc_id]}, {
                                                    'Name': 'tag:Name', 'Values': ['SharedExternalRouteTable']}, {'Name': 'tag:AZ', 'Values': [zonename]}])
            result[zonename] = response['RouteTables'][0]['RouteTableId']
        return result
    elif route_table_type == 'i':
        for zonename in zonenames:
            response = client.describe_route_tables(Filters=[{'Name': 'tag:VPC', 'Values': [vpc_id]}, {
                                                    'Name': 'tag:Name', 'Values': ['SharedInternalRouteTable']}, {'Name': 'tag:AZ', 'Values': [zonename]}])
            result[zonename] = response['RouteTables'][0]['RouteTableId']
        return result


def CreateSubnet(subnetsets, vpc_id, stackname):
    result = {}

    ec2 = boto3.resource('ec2')
    vpc = ec2.Vpc(vpc_id)
    for item in subnetsets['subnet']:
        az = item['az']
        az = GetAz(az)
        capacity = int(item['capacity']) + 5
        if capacity < 16:
            capacity = 16
        vpc_cidr = vpc_subnet.get_vpc_cidr(vpc_id)
        allocated_cidr = vpc_subnet.get_subnet_cidr(vpc_id)
        network = ipam.IPAM(vpc_cidr[0])
        unallocated = vpc_cidr
        for ip in allocated_cidr:
            tmplist = network_subtract.network_subtract(
                unallocated, [ip])
            unallocated = []
            for ip in tmplist:
                ip = str(ip)
                unallocated.append(ip)
        del network.unallocated[:]
        for ip in unallocated:
            network.unallocated.append(netaddr.IPNetwork(ip))
        network.update()
        subnet_cidr = network.add(capacity)
        tag = str(item['fuc']) + ':' + subnet_cidr + ':' + az.split("-")[2]
        subnet = vpc.create_subnet(AvailabilityZone=az, CidrBlock=subnet_cidr)
        result[str(item['fuc']) + "-" + az.split("-")[2] +
               '-SubnetId'] = subnet.subnet_id
        result[str(item['fuc']) + "-" + az.split("-")
               [2] + '-CIDR'] = subnet_cidr
        result[str(item['fuc']) + "-" + az.split("-")[2] + '-AZ'] = az
        client = boto3.client('ec2')
        client.create_tags(Resources=[subnet.subnet_id], Tags=[{'Key': 'Name', 'Value': tag}, {
            'Key': 'Stack', 'Value': stackname}])
        routetable = GetRouteTable(item['route'], vpc_id)
        print ('Subnet %s is created' % subnet_cidr)
        if not(item['route'] in ['p', 'e', 'i']):
            print ('Route requirement %s is wrong. should be one of (p,e,i)' %
                   item['route'])
            break
        else:
            if item['route'] == 'p':
                route_table = ec2.RouteTable(routetable)
                route_table.associate_with_subnet(SubnetId=subnet.subnet_id)
            if item['route'] == 'e':
                route_table = ec2.RouteTable(routetable[az])
                route_table.associate_with_subnet(SubnetId=subnet.subnet_id)
            if item['route'] == 'i':
                route_table = ec2.RouteTable(routetable[az])
            route_table.associate_with_subnet(SubnetId=subnet.subnet_id)
            print ('Route table  %s is associated to subnet %s' %
                   (str(route_table.route_table_id), subnet_cidr))

    print result
    return result


def DeleteSubnet(stackid):
    subnetids = []
    subnetids = vpc_subnet.get_subnet_ids('Stack', stackid)
    print ('Strating to delete subnets: %s' % str(subnetids))
    client = boto3.client('ec2')
    for id in subnetids:
        try:
            response = client.delete_subnet(SubnetId=id)
        except Exception as e:
            print e


def sendresponse(event, context, responsestatus, responsedata, reason):
    """Send a Success or Failure event back to CFN stack"""
    payload = {
        'StackId': event['StackId'],
        'Status': responsestatus,
        'Reason': reason,
        'RequestId': event['RequestId'],
        'LogicalResourceId': event['LogicalResourceId'],
        'PhysicalResourceId': event['LogicalResourceId'] +
        ''.join(random.SystemRandom().choice(string.ascii_uppercase + string.digits)
                for _ in range(10)),
        'Data': responsedata
    }
    if debug == "True":
        print "Sending %s to %s" % (json.dumps(payload), event['ResponseURL'])
    requests.put(event['ResponseURL'], data=json.dumps(payload))
    print "Sent %s to %s" % (json.dumps(payload), event['ResponseURL'])


# Function Test:
# a = SubnetParameters(
#    'f5:10:1a:p,f5:10:1b:p,web:20:1a:e,web:20:1b:e,app:30:1a:e,app:30:1b:e,db:15:1a:i,db:15:1b:i')

# print a
# b = CreateSubnet(a, 'vpc-00ecc594a15f1d36c',
#                 'arn:aws-cn:cloudformation:cn-north-1:238303532267:stack/t0/eb08b480-5042-11e8-b369-500c954b4a4b')
# print b
# DeleteSubnet(
#     'arn:aws-cn:cloudformation:cn-north-1:238303532267:stack/t0/eb08b480-5042-11e8-b369-500c954b4a4b')


def handler(event, context):
    """ Attempt to allocate CIDR ranges and create subnets """

    print "Started execution of Autosubnet Lambda..."
    print "Function ARN %s" % context.invoked_function_arn
    print "Incoming Event %s " % json.dumps(event)
    global debug

    stack_id = ''

    vpcid = ''
    requesttype = ''

    try:  # attempt to set debug status from CFN config - otherwise true
        debug = event['ResourceProperties']['debug']
    except Exception:
        debug = "False"

    if debug == "True":  # Print context and event - only if debug
        print event
        print context

    try:  # get subnet parameter, if not-present FAIL
        subnetparameters = event['ResourceProperties']['SubnetParameters']
    except Exception:
        sendresponse(event, context, 'FAILED', {
                     'Error': 'Subnet Parameter not provided'}, "Subnet Parameter not provided")
        return
    try:  # get subnet parameter, if not-present FAIL
        vpcstackname = event['ResourceProperties']['VpcStackName']
    except Exception:
        sendresponse(event, context, 'FAILED', {
                     'Error': 'VpcStackName Parameter not provided'}, "VpcStackName Parameter not provided")
        return
    try:  # get stack name, if not-present FAIL
        stack_id = event['StackId']
    except Exception:
        sendresponse(event, context, 'FAILED', {
                     'Error': 'Cannot get stack information'}, "Cannot get stack information")
        return
    try:  # Check that sharedinfrastructure VPC ID has been provided by template, if not, FAIL
        vpcid = event['ResourceProperties']['VpcId']
    except Exception:
        sendresponse(event, context, 'FAILED', {
                     'Error': 'Cannot find VPC.'}, "Cannot find VPC.")
        return
    try:  # Check that we can determine request type ... interested in CREATE or DELETE
        requesttype = event['RequestType']
    except Exception:
        sendresponse(event, context, 'FAILED', {
                     'Error': 'Cant determine request type.'}, "Cant determine request type.")
    if debug == "True":
        print "Past Input Checking"
    if requesttype == 'Delete':  # if delete, remove the subnet allocations, for this stackname
        if debug == 'True':
            print "Delete Requesttype Processing Started"
        try:
            DeleteSubnet(stack_id)
        except Exception as e:
            print e
            sendresponse(event, context, 'FAILED', {
                         'Error': 'Cannot delete subnets: %s' % str(e)}, "Cannot delete subnets.")
            return
        sendresponse(event, context, 'SUCCESS', {}, "")
        return

    if debug == "True":
        print "Create Requesttype Processing Started"

    if debug == "True":
        print "Starting to create subnets"

    responsedata = {}  # dictionary to store our return data
    try:
        parameter = SubnetParameters(subnetparameters)
    except Exception as e:
        print e
        sendresponse(event, context, 'FAILED', {
                     'Error': 'Cannot parse subnet parameter: %s' % str(e)}, "Cannot parse subnet parameter.")
        return
    print ('Start create subnet')
    print ('parameter=%s' % str(parameter))
    print ('vpcid=%s' % str(vpcid))
    print ('stack_id=%s' % str(stack_id))
    try:
        responsedata = CreateSubnet(parameter, vpcid, stack_id)
    except Exception as e:
        print e
        sendresponse(event, context, 'FAILED', {
                     'Error': 'Cannot create subnet: %s' % str(e)}, "Cannot create subnet.")
        return
    sendresponse(event, context, 'SUCCESS', responsedata, "N/A")
