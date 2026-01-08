# Team Project repo


## CI/CD Badges

**Develop Branch**
[![Build Status - develop](https://app.travis-ci.com/gcivil-nyu-org/team1-mon-fall25.svg?branch=develop)](https://app.travis-ci.com/github/gcivil-nyu-org/team1-mon-fall25/builds)
[![Coverage Status - develop](https://coveralls.io/repos/github/gcivil-nyu-org/team1-mon-fall25/badge.svg?branch=develop)](https://coveralls.io/github/gcivil-nyu-org/team1-mon-fall25?branch=develop)

**Main Branch**
[![Build Status - main](https://app.travis-ci.com/gcivil-nyu-org/team1-mon-fall25.svg?branch=main)](https://app.travis-ci.com/github/gcivil-nyu-org/team1-mon-fall25/builds)
[![Coverage Status - main](https://coveralls.io/repos/github/gcivil-nyu-org/team1-mon-fall25/badge.svg?branch=main)](https://coveralls.io/github/gcivil-nyu-org/team1-mon-fall25?branch=main)

## Deployment Notes

Simpletix was deplored on AWS using elastic beanstalk. The following AWS services had these specific resources associated with them:


### Elastic Beanstalk

1. **Platform**: Python 3.13 running on 64bit Amazon Linux 2023/4.7.3

1. **Environment**: `simpletix-dev`

    - Environment properties _(plain text)_ :
        
        - `ALGOLIA_SECRETS_NAME`: SimpleTixDevAlgoliaSecrets
        - `AWS_MEDIA_BUCKET_NAME`: simpletix-dev-media
        - `AWS_REGION`: us-east-1
        - `DB_SECRETS_NAME`: SimpleTixDevDBSecrets
        - `DJANGO_SECRET_KEY_NAME`: SimpleTixDevDjangoSecretKey
        - `EMAIL_SECRETS_NAME`: SimpleTixDevEmailSecrets
        - `ENVIRONMENT`: development
        - `GOOGLE_MAPS_SECRETS_NAME`: SimpleTixDevGoogleMapsAPIKey
        - `PYTHONPATH`: /var/app/venv/staging-LQM1lest/bin
        - `STRIPE_SECRETS_NAME`: SimpleTixDevStripeSecrets

1. **Environment**: `simpletix-prod`

    - Environment properties _(plain text)_ :
            
        - `ALGOLIA_SECRETS_NAME`: SimpleTixProdAlgoliaSecrets
        - `AWS_MEDIA_BUCKET_NAME`: simpletix-prod-media
        - `AWS_REGION`: us-east-1
        - `DB_SECRETS_NAME`: SimpleTixProdDBSecrets
        - `DJANGO_SECRET_KEY_NAME`: SimpleTixProdDjangoSecretKey
        - `EMAIL_SECRETS_NAME`: SimpleTixProdEmailSecrets
        - `ENVIRONMENT`: production
        - `GOOGLE_MAPS_SECRETS_NAME`: SimpleTixProdGoogleMapsAPIKey
        - `PYTHONPATH`: /var/app/venv/staging-LQM1lest/bin
        - `STRIPE_SECRETS_NAME`: SimpleTixProdStripeSecrets


### RDS

1. `simpletix-dev-db`
    - postgres 17.4
    - db.t3.micro
    - General Purpose SSD (gp3) 200 GiB
 
1. `simpletix-prod-db`
    - postgres 17.4
    - db.t3.micro
    - General Purpose SSD (gp3) 200 GiB

### S3

- Bucket Names:
    1. `simpletix-dev-media`

    1. `simpletix-prod-media`

 - Bucket Folder Structure:

    ```
    banners/
    event_videos/
    profile_photos/
    profiles/
    ```

### Secrets Manager

#### Simpletix Dev Secrets:
1. `SimpleTixDevEmailSecrets`
    - SMTP Email credentials dev
    - `SMTP_USER`: noreply.simpletix@gmail.com
    - `SMTP_PASSWORD`: ********
1. `SimpleTixDevStripeSecrets`
    - Secrets for Stripe Dev
    - `STRIPE_PUBLISHABLE_KEY`
    - `STRIPE_SECRET_KEY`
    - `STRIPE_WEBHOOK_SECRET`
    - Values for above can be generated using the directions from [PR 116](https://github.com/gcivil-nyu-org/team1-mon-fall25/pull/116)
1. `SimpleTixDevGoogleMapsAPIKey`
    - Google Maps Api Key Dev
    - `GOOGLE_MAPS_API_KEY`
    - Values for above can be generated using the directions from [PR 122](https://github.com/gcivil-nyu-org/team1-mon-fall25/pull/122)
1. `SimpleTixDevAlgoliaSecrets`
    - Access keys for Algolia search dev
    - `ALGOLIA_APP_ID`
    - `ALGOLIA_API_KEY`
    - `ALGOLIA_INDEX_PREFIX`
    - `ALGOLIA_SEARCH_KEY`
    - Values for above can be generatred using the directions from [PR 97](https://github.com/gcivil-nyu-org/team1-mon-fall25/pull/97)
1. `SimpleTixDevDBSecrets`
    - `username`: postgres
    - `password`: ********
    - `engine`: postgres
    - `host`: simpletix-dev-db.[PLACEHOLDER_SPECIFIC_INSTANCE_ID].[PLACEHOLDER_AWS_REGION].rds.amazonaws.com
    - `port`: 5432
    - `dbInstanceIdentifier`: simpletix-dev-db
    - `dbname`: simpletix
1. `SimpleTixDevDjangoSecretKey`
    - SECRET_KEY for Django dev
    - `SECRET_KEY`: ********

#### Simpletix Prod Secrets:
1. `SimpleTixDevEmailSecrets`
    - SMTP Email credentials dev
    - `SMTP_USER`: noreply.simpletix@gmail.com
    - `SMTP_PASSWORD`: ********
1. `SimpleTixProdStripeSecrets`
    - Secrets for Stripe Dev
    - `STRIPE_PUBLISHABLE_KEY`
    - `STRIPE_SECRET_KEY`
    - `STRIPE_WEBHOOK_SECRET`
    - Values for above can be generated using the directions from [PR 116](https://github.com/gcivil-nyu-org/team1-mon-fall25/pull/116)
1. `SimpleTixProdGoogleMapsAPIKey`
    - Google Maps Api Key Prod
    - `GOOGLE_MAPS_API_KEY`
    - Values for above can be generated using the directions from [PR 122](https://github.com/gcivil-nyu-org/team1-mon-fall25/pull/122)
1. `SimpleTixProdAlgoliaSecrets`
    - Access keys for Algolia search prod
    - `ALGOLIA_APP_ID`
    - `ALGOLIA_API_KEY`
    - `ALGOLIA_INDEX_PREFIX`
    - `ALGOLIA_SEARCH_KEY`
    - Values for above can be generatred using the directions from [PR 97](https://github.com/gcivil-nyu-org/team1-mon-fall25/pull/97)
1. `SimpleTixProdDBSecrets`
    - `username`: postgres
    - `password`: ********
    - `engine`: postgres
    - `host`: simpletix-prod-db.[PLACEHOLDER_SPECIFIC_INSTANCE_ID].[PLACEHOLDER_AWS_REGION].rds.amazonaws.com
    - `port`: 5432
    - `dbInstanceIdentifier`: simpletix-prod-db
    - `dbname`: simpletix
1. `SimpleTixProdDjangoSecretKey`
    - SECRET_KEY for Django prod
    - `SECRET_KEY`: ********