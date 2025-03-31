Sufficiently fill out sbConfig.json when generated, specify paths to sound files following PK3 directories.
Do not point to sound files used on your local system or server. Check MBII asset PK3s for their internal filepathing.
You may also do dir sound in console to get a readout of ALL potential sounds that can be used.

Server and Client must share the same files, you cannot use custom ones not supported by Moviebattles, unless you are a third party team with distribution.

Set values in sbConfig.json to "void" if you wish to avoid specific usecases.

Ensure file extension (.mp3/.wav) is included in the declared variables in the JSON config.
Ensure players playing on your server has cl_serversounds enabled to 1.

CREATED BY 2CWLDYS & VICEDICE