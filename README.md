# Bitbackup

Bitbackup backs up Bitbucket repositories to any S3 compatible data store.

## Features
- backs up all repositories of a team or user
- works with any s3 compatible store
- multi-threaded for performance
- low memory and storage requirements

## Basic Usage

```bash
docker run -it myriadmobile/bitbackup \
  --bb-username BB_USERNAME \
	--bb-password BB_PASSWORD \
	--s3-key S3_KEY \
	--s3-secret S3_SECRET \
	--s3-bucket S3_BUCKET
```

## Configuration
```bash
usage: main.py [-h] --bb-username BB_USERNAME --bb-password BB_PASSWORD
               --s3-key S3_KEY --s3-secret S3_SECRET --s3-bucket S3_BUCKET
               [--s3-base-path S3_BASE_PATH] [--s3-endpoint S3_ENDPOINT]
               [--workers WORKER_COUNT] [--debug]

Backup Bitbucket repositories to a S3 compatible store.

optional arguments:
  -h, --help            show this help message and exit
  --bb-username BB_USERNAME
                        Bitbucket username or team name
  --bb-password BB_PASSWORD
                        Bitbucket password or team API key
  --s3-key S3_KEY       S3 Access Key
  --s3-secret S3_SECRET
                        S3 Secret Key
  --s3-bucket S3_BUCKET
                        S3 Bucket
  --s3-base-path S3_BASE_PATH
                        S3 base path
  --s3-endpoint S3_ENDPOINT
                        S3 host
  --workers WORKER_COUNT
                        The number of worker threads
  --debug               Print debug messages
```

## Deploying with Fleet

Note, this section assumes that you can access the Fleet cluster via SSH or console access.

### Clone the Repository

Log in to the cluster and clone the Bitbackup repository:

```bash
https://github.com/myriadmobile/bitbackup.git
```

### Edit the Unit File

Edit `contrib/bitbackup.service` and replace the `REPLACE_ME`s with your Bitbucket and S3 details.
See the full usage above for additional configuration parameters.

Be default, Bitbackup will run nightly at 12:00am UTC. This can be changed by editing `contrib/bitbackup.timer`.
See http://www.freedesktop.org/software/systemd/man/systemd.timer.html for more information on timer files.

### Install the Units

Next we need to submit the unit files to the cluster using fleetctl.

```bash
cd contrib
fleetctl submit bitbackup.service
fleetctl submit bitbackup.timer
```

Now, start the timer:

```bash
fleetctl start bitbackup.timer
```

Note, this will only start the timer, which will start Bitbackup at the defined time. You can always manually start a backup:
 
```bash
fleetctl start bitbackup.service
```

### View the output of the backup

```bash
fleetctl journal -u bitbackup.service
```