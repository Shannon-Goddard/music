import sys
import boto3
from boto3.dynamodb.conditions import Attr

table = boto3.resource('dynamodb', region_name='us-east-1').Table('music-tracks')
deleted = 0

while True:
    found_any = False
    kwargs = {'FilterExpression': Attr('source_platform').eq('ccmixter')}
    while True:
        resp = table.scan(**kwargs)
        items = resp.get('Items', [])
        if items:
            found_any = True
            with table.batch_writer() as batch:
                for item in items:
                    batch.delete_item(Key={'track_id': item['track_id']})
                    deleted += 1
        last = resp.get('LastEvaluatedKey')
        if not last:
            break
        kwargs['ExclusiveStartKey'] = last
    sys.stdout.write(f'pass complete — deleted {deleted} so far...\n')
    sys.stdout.flush()
    if not found_any:
        break

# Full paginated count to confirm zero
remaining = 0
kwargs = {'FilterExpression': Attr('source_platform').eq('ccmixter'), 'Select': 'COUNT'}
while True:
    resp = table.scan(**kwargs)
    remaining += resp['Count']
    last = resp.get('LastEvaluatedKey')
    if not last:
        break
    kwargs['ExclusiveStartKey'] = last

sys.stdout.write(f'Done. Wiped {deleted}. Remaining ccmixter: {remaining}\n')
sys.stdout.flush()
