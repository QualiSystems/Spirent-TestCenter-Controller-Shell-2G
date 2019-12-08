
![](https://github.com/QualiSystems/cloudshell-shells-documentaion-templates/blob/master/cloudshell_logo.png)

# **Spirent testCenter Controller 2G Shell**  

Release date: December 2019

Shell version: 2.0.1

Document version: 1.0

# In This Guide

* [Overview](#overview)


# Overview
A shell integrates a device model, application or other technology with CloudShell. A shell consists of a data model that defines how the device and its properties are modeled in CloudShell, along with automation that enables interaction with the device via CloudShell.

### Traffic Generator Shells
CloudShell's traffic generator shells enable you to conduct traffic test activities on Devices Under Test (DUT) or Systems Under Test (SUT) from a sandbox. In CloudShell, a traffic generator is typically modeled using a chassis resource, which represents the traffic generator device and ports, and a controller service that runs the chassis commands, such as Load Configuration File, Start Traffic and Get Statistics. Chassis and controllers are modeled by different shells, allowing you to accurately model your real-life architecture. For example, scenarios where the chassis and controller are located on different machines.

For additional information on traffic generator shell architecture, and setting up and using a traffic generator in CloudShell, see the [Traffic Generators Overview](http://help.quali.com/Online%20Help/9.0/Portal/Content/CSP/LAB-MNG/Trffc-Gens.htm?Highlight=traffic%20generator%20overview) online help topic.

### **Spirent TestCenter Controller 2G Shell**
The **Spirent TestCenter Controller 2G** shell provides you with test control functionality equivalent to **Spirent TestCenter Application**. 
The controller provides automation commands to run on **TestCenter Chassis** shell, such as Load Configuration, Start/Stop Traffic, Get Statistics.
For more information on the **Spirent Chassis** shell, see the following:

* [Spirent Chassis 2G Shell](https://community.quali.com/repos/4894/spirent-testcenter-chassis-shell-2g)

For more information on the **Spirent TestCenter Application**, see the official **Spirent** product documentation.

### Standard version
The **Spirent TestCenter Controller 2G** shell is based on the Traffic Generator Controller Standard version 2.0.0.

For detailed information about the shell’s structure and attributes, see the [Traffic Shell standard](https://github.com/QualiSystems/shell-traffic-standard/blob/master/spec/traffic_standard.md) in GitHub.

### Supported OS
▪ Windows

### Requirements

**Spirent TestCenter Controller 2G** was tested with the following versions:

▪ STC REST Server: 4.94 and up

▪ CloudShell version: 9.3 and up

### Automation
This section describes the automation (driver) associated with the data model. The shell’s driver is provided as part of the shell package. There are two types of automation processes, Autoload and Resource.  Autoload is executed when creating the resource in the **Inventory** dashboard, while resource commands are run in the sandbox.

For Traffic Generator shells, commands are configured and executed from the controller service in the sandbox, with the exception of the Autoload command, which is executed when creating the resource.

|Command|Description|
|:-----|:-----|
|Load Configuration|Loads configuration and reserves ports.<br>Set the command input as follows:<br>* **STC config file name** (String): Full path to the STC configuration file name.|
|Start ARP/ND|Send ARP/ND for all protocols.|
|Start Devices|Starts all devices.|
|Stop Devices|Stops all devices.|
|Start Traffic|Starts L2-3 traffic.<br>Set the command input as follows:<br>* **Blocking**:<br>  - **True**: Returns after traffic finishes to run<br>  - **False**: Returns immediately|
|Stop Traffic|Stops L2-L3 traffic.|
|Get Statistics|Gets view statistics.<br>Set the command input as follows:<br>* **View Name**:<br>  -  GeneratorPortResults, TxStreamResults,  etc.<br>* **Output type**:<br>  -  **CSV**:<br>  -  **JSON**:<br>If **CSV**, the statistics will be attached to the blueprint csv file.|
|Run Sequencer|Runs qequencer.<br>Set the command inputs as follows:<br>* **Command**:<br>  -  **Start** - Start sequencer<br>  -  **Stop** - Stop sequencer<br>  -  **Wait** - Wait for sequencer.|
