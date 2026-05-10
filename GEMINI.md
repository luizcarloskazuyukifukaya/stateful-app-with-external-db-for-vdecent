# Application design
- The application should have a database to store application data
- Side car container to be introduced, that works independent from the applicatoin main code, and its purpose is to take backup/restore of the database to/from external storage.
- The external storage should be defined by the environment variables in .env. As a default, the external storage should be Google Drive. Thus, the Google Account and necessary token should be defined.
- The backup of the database should be defined by the environment variable, and the value that can be specified is 5 minutes. If the value specified is less than the minimum, it default to the minimu.
- The sidecar container should support API to trigger backup,restore and purge. Like /api/backup, /api/restore, /api/purge. For restore and purge, there should be an mechanism to secure the execution to only allow authorized request.
- The backups are to be purged based on the environment valuable defined in the .env, it should indicate how many backups are to be stored. For example, if it is 5, then always we will have 5 backups in the storage and privious will be deleted. If the environment valuable is not defined, all backups will be kept automatically.
- Upon the first deployment of the application, the sidecar should trigger restoration of the latest backup to the database making sure the database service is running before.
