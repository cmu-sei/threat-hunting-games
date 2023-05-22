﻿// Copyright 2017 Carnegie Mellon University. All Rights Reserved. See LICENSE.md file for terms.

using System;
using System.Diagnostics;
using Ghosts.Domain;
using NLog;

namespace Ghosts.Client.Infrastructure
{
    public static class GuestInfoVars
    {
        private static readonly Logger _log = LogManager.GetCurrentClassLogger();

        public static void Load(ResultMachine machine)
        {
            //if configured, try to set machine.name based on some vmtools.exe value
            try
            {
                if (Program.Configuration.IdFormat.Equals("guestinfo", StringComparison.InvariantCultureIgnoreCase))
                {
                    var p = new Process
                    {
                        StartInfo =
                        {
                            UseShellExecute = false,
                            RedirectStandardOutput = true,
                            FileName = $"{Program.Configuration.VMWareToolsLocation}",
                            Arguments = $"--cmd \"info-get {Program.Configuration.IdFormatKey}\""
                        }
                    };
                    
                    p.Start();

                    var output = p.StandardOutput.ReadToEnd().Trim();
                    p.WaitForExit();

                    if (!string.IsNullOrEmpty(output))
                    {
                        var o = Program.Configuration.IdFormatValue;
                        o = o.Replace("$formatkeyvalue$", output);
                        o = o.Replace("$machinename$", machine.Name);

                        machine.SetName(o);
                    }
                }
            }
            catch (Exception e)
            {
                _log.Debug(e);
            }
        }
    }
}
