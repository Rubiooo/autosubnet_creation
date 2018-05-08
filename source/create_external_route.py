import boto3
import json
import requests
import random
import time
import copy
import string


def DeleteExternalRoute(client, stackid):
    filter = [{'Name': 'tag:Stack', 'Values': [stackid]},
              {'Name': 'tag:Name', 'Values': ['SharedExternalRouteTable']}]

    try:
        response = client.describe_route_tables(Filters=filter)
    except Exception as e:
        print e
        return
    for rt in response['RouteTables']:
        print('Deleting route 0.0.0.0/0 in route table %s' %
              rt['RouteTableId'])
        try:
            response = client.delete_route(
                DestinationCidrBlock='0.0.0.0/0', RouteTableId=rt['RouteTableId'])
        except Exception as e:
            print e
            return


def GetNATId(client, az, stackid):
    filter = [{'Name': 'tag:Stack', 'Values': [stackid]},
              {'Name': 'tag:AZ', 'Values': [az]}]
    try:
        response = client.describe_nat_gateways(Filters=filter)
    except Exception as e:
        print e
        return
    return response['NatGateways'][0]['NatGatewayId']


def CreateExtRoute(client, netgatewayid, eroutetableid):
    result = []
    wait = "True"
    try:
        externalroute = client.create_route(
            DestinationCidrBlock='0.0.0.0/0', NatGatewayId=str(netgatewayid), RouteTableId=str(eroutetableid))
    except:
        while (wait == "True"):
            print ('Checking whether NAT %s is ready' % netgatewayid)
            try:
                gw = client.describe_nat_gateways(
                    NatGatewayIds=[netgatewayid])
            except Exception as e:
                print e
                sendresponse(event, context, 'FAILED', {
                    'Error': 'Cannot get NAT Gateway status: %s' % str(e)}, "NAT status")

            if gw['NatGateways'][0]['State'] == 'available':
                wait = ''
                break
            else:
                time.sleep(2)
        try:
            externalroute = client.create_route(
                DestinationCidrBlock='0.0.0.0/0', NatGatewayId=str(netgatewayid), RouteTableId=str(eroutetableid))
        except Exception as e:
            print e
            sendresponse(event, context, 'FAILED', {
                'Error': 'Cannot create external route: %s' % str(e)}, "external route")
            return
    return externalroute


def AddNATtoExtRTB(client, stackid):
    filter = [{'Name': 'tag:Stack', 'Values': [stackid]}, {
        'Name': 'tag:Name', 'Values': ['SharedExternalRouteTable']}]
    try:
        response = client.describe_route_tables(Filters=filter)
    except Exception as e:
        print e
        return
    print ('Start to add route to route tables:')
    for rt in response['RouteTables']:
        for tag in rt['Tags']:
            if tag["Key"] == 'AZ':
                az = tag["Value"]
        netgatewayid = GetNATId(client, az, stackid)
        print ('az: %s, netgatewayid: %s, RT id: %s' %
               (az, netgatewayid, rt['RouteTableId']))
        CreateExtRoute(client, netgatewayid, rt['RouteTableId'])


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


def handler(event, context):
    responsedata = {}
    client = boto3.client('ec2')
    print "Started execution of add routes to external route table Lambda..."
    print "Function ARN %s" % context.invoked_function_arn
    print "Incoming Event %s " % json.dumps(event)
    global debug
    try:  # attempt to set debug status from CFN config - otherwise true
        debug = event['ResourceProperties']['debug']
    except Exception:
        debug = "False"

    if debug == "True":  # Print context and event - only if debug
        print event
        print context
    try:  # get stack name, if not-present FAIL
        stackid = event['ResourceProperties']['StackId']
    except Exception:
        sendresponse(event, context, 'FAILED', {
            'Error': 'Stack ID not provided'}, "Stack ID not provided")
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
            DeleteExternalRoute(client, stackid)
        except Exception as e:
            print e
            sendresponse(event, context, 'FAILED', {
                         'Error': 'Cannot delete external route: %s' % str(e)}, "Cannot delete external route.")
            return
        sendresponse(event, context, 'SUCCESS', {}, "")
        return
    try:
        responsedata = AddNATtoExtRTB(client, stackid)
    except Exception as e:
        print e
        sendresponse(event, context, 'FAILED', {
            'Error': 'Create exteral route failed'}, "Create exteral route failed")
        return
    sendresponse(event, context, 'SUCCESS', responsedata, "N/A")
