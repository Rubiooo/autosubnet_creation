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


def SubnetParameters(input):
    # input example:   tag:capacity:AZ(1a, 1b):public(p),external(e) or internal(i),
    SubnetSets = {"subnet": []}
    detail = {}
    SubnetList = input.split(',')

    for i in range(0, len(SubnetList)):
        tmp = SubnetList[i].split(':')
        detail['fuc'] = tmp[0]
        detail['capacity'] = tmp[1]
        detail['az'] = tmp[2]
        detail['route'] = tmp[3]
        d = copy.deepcopy(detail)
        SubnetSets['subnet'].append(d)
    return SubnetSets

# Function Test:
# a = SubnetParameters('web1:50:1a:p,web2:50:1a:p')
# print a


def GetAz(az):
    client = boto3.client('ec2')
    response = client.describe_availability_zones()
    # print az
    # print response['AvailabilityZones']
    for item in response['AvailabilityZones']:
        if az in item['ZoneName']:
            return item['ZoneName']
            break

# Function Test:
# print 'GetAz(az):'
# print item['ZoneName']
# print GetAz('1b')


def GetRouteTable(route_table_type, vpc_id):
    result = {}
    zonenames = []
    client = boto3.client('ec2')
    zones = client.describe_availability_zones()
    for az in zones['AvailabilityZones']:
        zonenames.append(az['ZoneName'])
    print zonenames
    if route_table_type == 'p':
        response = client.describe_route_tables(Filters=[{'Name': 'tag:VPC', 'Values': [
                                                vpc_id]}, {'Name': 'tag:Name', 'Values': ['PublicRouteTable']}])
        # print response['RouteTables'][0]['RouteTableId']
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
        # print result
        return result


def CreateSubnet(subnetsets, vpc_id, stackid):
    resultset = []
    result = {}
    ec2 = boto3.resource('ec2')
    client = boto3.client('ec2')
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
        tag = str(item['fuc']) + ':' + str(subnet_cidr) + ':' + str(az)
        subnet = vpc.create_subnet(
            AvailabilityZone=str(az), CidrBlock=str(subnet_cidr))
        result['SubnetId'] = subnet.subnet_id
        try:
            response = client.modify_subnet_attribute(SubnetId=subnet.subnet_id, MapPublicIpOnLaunch={
                'Value': True})
        except Exception as e:
            print (str(e))
        result['CIDR'] = subnet_cidr
        result['AZ'] = az
        try:
            client.create_tags(Resources=[subnet.subnet_id], Tags=[{'Key': 'Name', 'Value': tag}, {
                'Key': 'Stack', 'Value': stackid}])
        except Exception as e:
            print (str(e))
        tmp = copy.deepcopy(result)
        resultset.append(tmp)
    print resultset
    return resultset


def DeletePublicInfra(stackid):
    routetableids = []
    vpcendpointids = []
    natgatewayids = []

    subnetids = []
    subnetids = vpc_subnet.get_subnet_ids('Stack', stackid)
    print ("Delete Subnet %s: " % str(subnetids))
    routetableids = vpc_subnet.get_routetable_ids('Stack', stackid)
    print ("Delete Route Table ID: %s: " % str(routetableids))
    vpcendpointids = vpc_subnet.get_vpcendpoint_ids(routetableids)
    print ("Delete VPC Endpoints %s: " % str(vpcendpointids))
    natgatewayids = vpc_subnet.get_nat_gateway_ids('Stack', stackid)
    print ("Delete NAT Gateways %s: " % str(natgatewayids))
    netinterfaceids = []

    client = boto3.client('ec2')
    ec2 = boto3.resource('ec2')
    try:
        response = client.describe_route_tables(Filters=[{'Name': 'tag:Name', 'Values': [
            'PublicRouteTable']}, {'Name': 'tag:Stack', 'Values': [stackid]}])
    except Exception as e:
        print ('Cannot find route table: %s' % str(e))
    for rt in response['RouteTables']:
        if len(rt['Associations']) != 0:
            for a in rt['Associations']:
                rt_association_id = a['RouteTableAssociationId']
                ec2.RouteTableAssociation(rt_association_id).delete()
                print ('Delete route table %s association: ' %
                       rt['RouteTableId'])

    try:
        response = client.delete_vpc_endpoints(VpcEndpointIds=vpcendpointids)
        print ('VPC Endpoint is deleted: %s' % str(vpcendpointids))
    except Exception as e:
        print ('VPC endpoints cannot be deleted or does not exit:  %s' % str(e))

    for id in natgatewayids:
        try:
            response = client.delete_nat_gateway(NatGatewayId=id['id'])
            print ('NAT Gateway is deleted: %s' % str(id['id']))
        except Exception as e:
            print ('NAT Gateway %s cannot be deleted or does not exit: %s' %
                   (str(id['id']), str(e)))
            break
    for id in natgatewayids:
        i = 0
        while True:
            try:  # if NAT is noy deleted, then describe_network_interfaces can be executed successfully
                response = client.describe_network_interfaces(
                    NetworkInterfaceIds=[id['networkinterface']])
            except:
                i = i + 1
                time.sleep(2)
                try:
                    response = client.release_address(
                        AllocationId=id['allocationId'])
                    print 'EIP is deleted'
                    break
                except:
                    if i == 60:
                        print 'EIP cannot be deleted'
                        break
    for id in subnetids:
        try:
            response = client.delete_subnet(SubnetId=id)
            print ('Subnet is deleted- %s' % str(id))
        except Exception as e:
            print ('Subnet cannot be deleted or does not exit: %s' % str(e))
    for id in routetableids:
        try:
            response = client.delete_route_table(RouteTableId=id)
            print ('Route table is deleted: %s' % str(id))
        except Exception as e:
            print ('Route table cannot be deleted or does not exit:  %s' % str(e))


def CreateNatGateway(subnetid):

    allocatedip = {}
    client = boto3.client('ec2')
    try:
        allocatedip = client.allocate_address(Domain='vpc')
    except Exception as e:
        print ('Cannot allocate Elastic IP address: %s' % str(e))
        return
    eip = allocatedip['AllocationId']
    print ('NAT Gateway EIP: %s is created successfully' % str(eip))
    try:
        response = client.create_nat_gateway(
            AllocationId=eip, SubnetId=subnetid)
    except Exception as e:
        print ('Cannot create NAT Gateway %s' % str(e))
        return
    print ('NAT Gateway: %s is created successfully' %
           str(response['NatGateway']['NatGatewayId']))
    return response['NatGateway']['NatGatewayId']


# Function Test:
# a = SubnetParameters('web1:50:1a:p,web2:50:1a:p')
# print a
# b = CreateSubnet(a, 'vpc-0213f95c9df89bf1a', 'vpcdemo')
# print b
# DeleteSubnet('TESTSTACK')
# DeletePublicInfra(
#     'arn:aws-cn:cloudformation:cn-north-1:238303532267:stack/s0/e5f00e20-5084-11e8-bdce-50d5cdfd10fa')


def handler(event, context):
    """ Attempt to allocate CIDR ranges and create subnets """

    print "Started execution of Autosubnet Lambda..."
    print "Function ARN %s" % context.invoked_function_arn
    print "Incoming Event %s " % json.dumps(event)
    global debug

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
        networkcapacity = event['ResourceProperties']['NetWorkCapacity']
    except Exception:
        sendresponse(event, context, 'FAILED', {
                     'Error': 'Subnet Parameter is wrong'}, "Subnet Parameter is wrong")
        return

    try:  # get stack name, if not-present FAIL
        stackid = event['ResourceProperties']['StackId']
    except Exception:
        sendresponse(event, context, 'FAILED', {
                     'Error': 'Stack ID not provided'}, "Stack ID not provided")
        return

    try:  # Check that sharedinfrastructure VPC ID has been provided by template, if not, FAIL
        vpcid = event['ResourceProperties']['VpcId']
    except Exception:
        sendresponse(event, context, 'FAILED', {
                     'Error': 'VPC ID not provided.'}, "VPC ID not provided.")
        return

    try:  # Check that region has been provided by template, if not, FAIL
        region = event['ResourceProperties']['Region']
    except Exception:
        sendresponse(event, context, 'FAILED', {
                     'Error': 'Region not provided.'}, "Regionnot provided.")
        return
    try:  # Check that we can determine request type ... interested in CREATE or DELETE
        requesttype = event['RequestType']
    except Exception:
        sendresponse(event, context, 'FAILED', {
                     'Error': 'Cant determine request type.'}, "Cant determine request type.")

    if requesttype == 'Delete':  # if delete, remove the subnet allocations, for this stackid
        if debug == 'True':
            print "Delete Requesttype Processing Started"
        try:
            DeletePublicInfra(stackid)
        except Exception as e:
            print e
            sendresponse(event, context, 'FAILED', {
                         'Error': 'Cannot delete public infrastructure: %s' % str(e)}, "Cannot delete public infrastructure.")
            return
        sendresponse(event, context, 'SUCCESS', {}, "")
        return

    if debug == "True":
        print "Starting Possible Subnet Iteration"

    responsedata = {}  # dictionary to store our return data
    SubnetSets = {"subnet": []}
    subnetparameters = {}
    netgatewayids = []
    eroutetableids = []
    iroutableids = []
    publicsubnetids = []
    client = boto3.client('ec2')
    try:
        response = client.describe_availability_zones()
    except Exception as e:
        print e
        sendresponse(event, context, 'FAILED', {
                     'Error': 'Cannot get AZ information: %s' % str(e)}, "Cannot get AZ information.")
        return
    for item in response['AvailabilityZones']:
        subnetparameters['fuc'] = 'PublicSubnet'
        subnetparameters['capacity'] = networkcapacity
        subnetparameters['az'] = item['ZoneName']
        d = copy.deepcopy(subnetparameters)
        SubnetSets['subnet'].append(d)
    try:
        subnets = CreateSubnet(SubnetSets, vpcid, stackid)
    except Exception as e:
        print e
        sendresponse(event, context, 'FAILED', {
            'Error': 'Cannot create Subnets: %s' % str(e)}, "Cannot create Subnets.")
        return
    for subnet in subnets:
        subnetid = subnet['SubnetId']
        publicsubnetids.append(subnetid)
        responsedata['PublicSubnetID-' + str(subnet['AZ'])] = subnetid
        try:
            routetable = GetRouteTable('p', vpcid)
        except Exception as e:
            print e
            sendresponse(event, context, 'FAILED', {
                'Error': 'Cannot get public route table ID: %s' % str(e)}, "Cannot get public route table ID.")
            return
        ec2 = boto3.resource('ec2')
        try:
            route_table = ec2.RouteTable(routetable)
        except Exception as e:
            print e
            sendresponse(event, context, 'FAILED', {
                'Error': 'Cannot find public route table: %s' % str(e)}, "Cannot fine public route table.")
            return
        try:
            route_table.associate_with_subnet(SubnetId=subnetid)
            print('Public route table %s is associated to subnet %s in %s' %
                  (str(routetable), subnetid, subnet['AZ']))
        except Exception as e:
            print e
            sendresponse(event, context, 'FAILED', {
                'Error': 'Cannot associate public route table: %s' % str(e)}, "Cannot associate public route table.")
            return
        try:
            netgatewayid = CreateNatGateway(subnetid)
        except Exception as e:
            print e
            sendresponse(event, context, 'FAILED', {
                'Error': 'Cannot create NatGateway: %s' % str(e)}, "Cannot create  NatGateway.")
            return

        try:
            netgatewaytag = client.create_tags(Resources=[netgatewayid], Tags=[{'Key': 'Name', 'Value': 'NatGateway'}, {
                'Key': 'Stack', 'Value': stackid}, {'Key': 'VPC', 'Value': vpcid}, {'Key': 'AZ', 'Value': subnet['AZ']}])

        except Exception as e:
            print e
            sendresponse(event, context, 'FAILED', {
                'Error': 'Cannot create tags: %s' % str(e)}, "Cannot create tags.")
            return
        netgatewayids.append(netgatewayid)

        try:
            eroutable = client.create_route_table(VpcId=vpcid)
        except Exception as e:
            print e
            sendresponse(event, context, 'FAILED', {
                'Error': 'Cannot create RouteTable: %s' % str(e)}, "Cannot create RouteTable.")
            return
        eroutetableid = eroutable['RouteTable']['RouteTableId']

        eroutetableids.append(eroutetableid)
        try:
            eeroutabletag = client.create_tags(Resources=[eroutetableid], Tags=[{'Key': 'Name', 'Value': 'SharedExternalRouteTable'}, {
                'Key': 'Stack', 'Value': stackid}, {'Key': 'VPC', 'Value': vpcid}, {'Key': 'AZ', 'Value': subnet['AZ']}])
        except Exception as e:
            print e
            sendresponse(event, context, 'FAILED', {
                'Error': 'Cannot create tags: %s' % str(e)}, "Cannot create tags.")
            return

        responsedata['ExternalRouteTable-' + str(subnet['AZ'])] = eroutetableid
        try:
            iroutable = client.create_route_table(VpcId=vpcid)
        except Exception as e:
            print e
            sendresponse(event, context, 'FAILED', {
                         'Error': 'Cannot create route table: %s' % str(e)}, "Cannot create route table.")
            return
        iroutetableid = iroutable['RouteTable']['RouteTableId']
        iroutableids.append(iroutetableid)
        try:
            iroutabletag = client.create_tags(Resources=[iroutetableid], Tags=[{'Key': 'Name', 'Value': 'SharedInternalRouteTable'}, {
                'Key': 'Stack', 'Value': stackid}, {'Key': 'VPC', 'Value': vpcid}, {'Key': 'AZ', 'Value': subnet['AZ']}])
        except Exception as e:
            print e
            sendresponse(event, context, 'FAILED', {
                'Error': 'Cannot create tags: %s' % str(e)}, "Cannot create tags.")
            return
        servicename = 'com.amazonaws.' + region + '.s3'
        try:

            s3endpoint = client.create_vpc_endpoint(VpcEndpointType='Gateway', ServiceName=servicename, VpcId=vpcid, RouteTableIds=[
                eroutetableid, iroutetableid])
        except Exception as e:
            print e
            sendresponse(event, context, 'FAILED', {
                'Error': 'Cannot create S3 endpoint: %s' % str(e)}, "Cannot create S3 endpoint.")
            return
        servicename = 'com.amazonaws.' + region + '.dynamodb'
        try:

            ddbendpoint = client.create_vpc_endpoint(VpcEndpointType='Gateway', ServiceName=servicename, VpcId=vpcid, RouteTableIds=[
                eroutetableid, iroutetableid])
        except Exception as e:
            print e
            sendresponse(event, context, 'FAILED', {
                'Error': 'Cannot create DynamoDB endpoint: %s' % str(e)}, "Cannot create DynamoDB endpoint.")
            return
        responsedata['InternalRouteTable-' + str(subnet['AZ'])] = iroutetableid
    sendresponse(event, context, 'SUCCESS', responsedata, "N/A")
