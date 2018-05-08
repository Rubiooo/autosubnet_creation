import boto3
import netaddr
import copy


def get_subnet_cidr(vpc_id):

    result = []
    subnets_collections = {}
    filters = [{'Name': 'vpc-id', 'Values': [vpc_id]}]
    client = boto3.client('ec2')
    try:
        subnets_collections = client.describe_subnets(Filters=filters)
    except Exception as e:
        print e
        return
    if len(subnets_collections['Subnets']) > 0:
        for item in subnets_collections['Subnets']:
            cidr = item['CidrBlock']
            result.append(cidr)
    return result


def get_vpc_cidr(vpc_id):
    ec2 = boto3.resource('ec2')
    try:
        vpc = ec2.Vpc(vpc_id)
    except Exception as e:
        print e
        return
    return [vpc.cidr_block]


def get_subnet_ids(name, value):
    result = []
    filtername = 'tag:' + str(name)
    client = boto3.client('ec2')
    try:
        response = client.describe_subnets(
            Filters=[{'Name': filtername, 'Values': [value]}])
    except Exception as e:
        print e
        return
    for subnet in response['Subnets']:
        result.append(subnet['SubnetId'])
    return result


def get_routetable_ids(name, value):
    result = []
    filtername = 'tag:' + str(name)
    client = boto3.client('ec2')
    try:
        response = client.describe_route_tables(
            Filters=[{'Name': filtername, 'Values': [value]}])
    except Exception as e:
        print e
        return
    for routeble in response['RouteTables']:
        result.append(routeble['RouteTableId'])
    return result


def get_nat_gateway_ids(name, value):
    result = []
    temp = {}
    filtername = 'tag:' + str(name)
    client = boto3.client('ec2')
    try:
        response = client.describe_nat_gateways(
            Filters=[{'Name': filtername, 'Values': [value]}])
    except Exception as e:
        print e
        return
    for gw in response['NatGateways']:
        # if gw['State'] == 'available':
        temp['id'] = gw['NatGatewayId']
        temp['networkinterface'] = gw['NatGatewayAddresses'][0]['NetworkInterfaceId']
        temp['allocationId'] = gw['NatGatewayAddresses'][0]['AllocationId']
        t = copy.deepcopy(temp)
        result.append(t)
    return result


def get_vpcendpoint_ids(routetableids):
    print ('Checking VPC Endpoints in these route tables: %s' %
           str(routetableids))
    result = []
    client = boto3.client('ec2')
    try:
        response = client.describe_vpc_endpoints()
    except Exception as e:
        print e
        return
    # print response['VpcEndpoints']
    for endpoint in response['VpcEndpoints']:
        for id in endpoint['RouteTableIds']:
            if id in routetableids:
                print ('Find endpoint in route table: %s' % id)
                result.append(endpoint['VpcEndpointId'])
    return result
