﻿using System;
using System.Collections.Generic;
using System.Linq;
using System.Text;
using System.Threading.Tasks;
using System.IO;
using System.Threading;
using Renci.SshNet;
using Ghosts.Client.Infrastructure;
using Ghosts.Domain;
using System.Net;
using System.Diagnostics;
using Newtonsoft.Json;

/*
 * Used Package Renci.sshNet
 * Installed via packag manager
 * Install-Package SSH.NET
 * 
 */

namespace Ghosts.Client.Handlers
{
    /// <summary>
    /// This handler connects to a remote host and executes SSH commands.
    /// This uses the Credentials class that keeps a simple dictionary of credentials
    /// For SSH, is  uses the Renci.sshNet package, install via PM with Install-Package SSH.NET
    /// The SSH connection uses a ShellStream for executing commands once a connection is established.
    /// Each SSH shell command can have reserved words in it, such as '[remotedirectory]' which 
    /// is replaced by a random remote directory on the server.  So 'cd [remotedirectory]' will change
    /// to a random remote directory. 
    /// See the Sample Timelines/Ssh.json for a sample timeline using this handler.
    /// </summary>
    public class Ssh : BaseHandler
    {

        private Credentials CurrentCreds = null;
        private SshSupport CurrentSshSupport = null;   //current SshSupport for this object

        public Ssh(TimelineHandler handler)
        {
            try
            {
                base.Init(handler);
                this.CurrentSshSupport = new SshSupport();
                if (handler.HandlerArgs != null)
                {
                    if (handler.HandlerArgs.ContainsKey("CredentialsFile"))
                    {
                        try
                        {
                            this.CurrentCreds = JsonConvert.DeserializeObject<Credentials>(File.ReadAllText(handler.HandlerArgs["CredentialsFile"].ToString()));
                        }
                        catch (Exception e)
                        {
                            Log.Error(e);
                        }
                    }
                    if (handler.HandlerArgs.ContainsKey("ValidExts"))
                    {
                        try
                        {
                            this.CurrentSshSupport.ValidExts = handler.HandlerArgs["ValidExts"].ToString().Split(';');
                        }
                        catch (Exception e)
                        {
                            Log.Error(e);
                        }
                    }
                    if (handler.HandlerArgs.ContainsKey("CommandTimeout"))
                    {
                        try
                        {
                            this.CurrentSshSupport.CommandTimeout = Int32.Parse(handler.HandlerArgs["CommandTimeout"].ToString());
                        }
                        catch (Exception e)
                        {
                            Log.Error(e);
                        }
                    }
                    if (handler.HandlerArgs.ContainsKey("TimeBetweenCommandsMax"))
                    {
                        try
                        {
                            this.CurrentSshSupport.TimeBetweenCommandsMax = Int32.Parse(handler.HandlerArgs["TimeBetweenCommandsMax"].ToString());
                            if (this.CurrentSshSupport.TimeBetweenCommandsMax < 0) this.CurrentSshSupport.TimeBetweenCommandsMax = 0;
                        }
                        catch (Exception e)
                        {
                            Log.Error(e);
                        }
                    }
                    if (handler.HandlerArgs.ContainsKey("TimeBetweenCommandsMin"))
                    {
                        try
                        {
                            this.CurrentSshSupport.TimeBetweenCommandsMin = Int32.Parse(handler.HandlerArgs["TimeBetweenCommandsMin"].ToString());
                            if (this.CurrentSshSupport.TimeBetweenCommandsMin < 0) this.CurrentSshSupport.TimeBetweenCommandsMin = 0;
                        }
                        catch (Exception e)
                        {
                            Log.Error(e);
                        }
                    }
                }



                if (handler.Loop)
                {
                    while (true)
                    {
                        Ex(handler);
                    }
                }
                else
                {
                    Ex(handler);
                }
            }
            catch (ThreadAbortException)
            {
                ProcessManager.KillProcessAndChildrenByName(ProcessManager.ProcessNames.Command);
                Log.Trace("Cmd closing...");
            }
            catch (Exception e)
            {
                Log.Error(e);
            }

        }
        public void Ex(TimelineHandler handler)
        {
            foreach (var timelineEvent in handler.TimeLineEvents)
            {
                WorkingHours.Is(handler);

                if (timelineEvent.DelayBefore > 0)
                    Thread.Sleep(timelineEvent.DelayBefore);

                Log.Trace($"SSH Command: {timelineEvent.Command} with delay after of {timelineEvent.DelayAfter}");

                switch (timelineEvent.Command)
                {
                    case "random":
                        while (true)
                        {
                            var cmd = timelineEvent.CommandArgs[_random.Next(0, timelineEvent.CommandArgs.Count)];
                            if (!string.IsNullOrEmpty(cmd.ToString()))
                            {
                                this.Command(handler, timelineEvent, cmd.ToString());
                            }
                            Thread.Sleep(timelineEvent.DelayAfter);
                        }
                    default:
                        this.Command(handler, timelineEvent, timelineEvent.Command);

                        foreach (var cmd in timelineEvent.CommandArgs)
                            if (!string.IsNullOrEmpty(cmd.ToString()))
                                this.Command(handler, timelineEvent, cmd.ToString());
                        break;
                }

                if (timelineEvent.DelayAfter > 0)
                    Thread.Sleep(timelineEvent.DelayAfter);
            }
        }


        public void Command(TimelineHandler handler, TimelineEvent timelineEvent, string command)
        {
            
            char[] charSeparators = new char[] { '|' };
            var cmdArgs = command.Split(charSeparators, 3,StringSplitOptions.None);
            var hostIp = cmdArgs[0];
            var credKey = cmdArgs[1];
            var sshCmds = cmdArgs[2].Split(';');
            var username = this.CurrentCreds.GetUsername(credKey);
            var password = this.CurrentCreds.GetPassword(credKey);
            Log.Trace("Beginning SSH to host:  " + hostIp + " with command: " + command);

            if (username != null && password != null)
            {
                
                //have IP, user/pass, try connecting 
                using (var client = new SshClient(hostIp, username, password))
                {
                    try
                    {
                        client.Connect();
                    }
                    catch (Exception e)
                    {
                        Log.Error(e);
                        return;  //unable to connect
                    }
                    //we are connected, execute the commands
                    ShellStream shellStreamSSH = client.CreateShellStream("vt220", 80, 60, 800, 600, 65536);
                    //before running commands, flush the input of welcome login text
                    this.CurrentSshSupport.GetSshCommandOutput(shellStreamSSH, true);
                    foreach (var sshCmd in sshCmds)
                    {
                        try
                        {
                            this.CurrentSshSupport.RunSshCommand(shellStreamSSH, sshCmd);
                        }
                        catch (Exception e)
                        {
                            Log.Error(e); //some error occurred during this command, try the next one
                        }
                    }
                    client.Disconnect();
                    client.Dispose();
                    this.Report(handler.HandlerType.ToString(), command, "", timelineEvent.TrackableId);
                }
            }

        }





    }

}
