TODO
====

* Event-log-page in web-service to show what has happened recently
* Switch to newer kafka
    * Balanced consumer for multi-instance support
    * Commit offset after deploy success
    * Use log-compacted topic, and start from smallest offset on startup
* The service_port and exposed_port must be the same for thrift services (aka NodePorts) otherwise the FW-rules gets really confusing
