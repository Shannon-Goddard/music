# Music Platform — AWS Resource Reference

## API Gateway
- API ID:    9jxmxtjybb
- Stage:     v1
- Base URL:  https://9jxmxtjybb.execute-api.us-east-1.amazonaws.com/v1

## Endpoints
- GET /tracks/search?q={query}&genre={genre}&limit={n}
- GET /radio?genre={genre}&limit={n}

## Lambda Functions
- music-search   arn:aws:lambda:us-east-1:170377509849:function:music-search
- music-radio    arn:aws:lambda:us-east-1:170377509849:function:music-radio

## DynamoDB
- Table:     music-tracks
- ARN:       arn:aws:dynamodb:us-east-1:170377509849:table/music-tracks

## IAM
- Role:      music-lambda-role
- ARN:       arn:aws:iam::170377509849:role/music-lambda-role

## Secrets Manager
- music/jamendo
- music/acoustid
- music/zenodo
- music/metabrainz
