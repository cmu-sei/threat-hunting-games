﻿// Copyright 2017 Carnegie Mellon University. All Rights Reserved. See LICENSE.md file for terms.

using Ghosts.Client.Infrastructure;
using Ghosts.Client.Handlers;
using Ghosts.Domain;
using Microsoft.Win32;
using NLog;
using System;
using System.Diagnostics;
using System.IO;
using System.Linq;
using System.Reflection;
using System.Threading;
using System.Security.Permissions;
using Ghosts.Domain.Code;
using Ghosts.Domain.Models;
// ReSharper disable RedundantAssignment

namespace Ghosts.Client.TimelineManager
{
    /// <summary>
    /// Translates timeline.config file events into their appropriate handler
    /// </summary>
    public class Orchestrator
    {
        private static readonly Logger _log = LogManager.GetCurrentClassLogger();
        private static DateTime _lastRead = DateTime.MinValue;
        private Thread MonitorThread { get; set; }
        private static Timeline _defaultTimeline;
        private FileSystemWatcher _timelineWatcher;
        private bool _isSafetyNetRunning;
        private bool _isTempCleanerRunning;

        private bool IsWordInstalled { get; set; }
        private bool IsExcelInstalled { get; set; }
        private bool IsPowerPointInstalled { get; set; }
        private bool IsOutlookInstalled { get; set; }

        [PermissionSet(SecurityAction.Demand, Name ="FullTrust")]
        public void Run()
        {
            try
            {
                _defaultTimeline = TimelineBuilder.GetLocalTimeline();

                if (_isSafetyNetRunning != true) //checking if safetynet has already been started
                {
                    this.StartSafetyNet(); //watch instance numbers
                    _isSafetyNetRunning = true;
                }

                if (_isTempCleanerRunning != true) //checking if tempcleaner has been started
                {
                    TempFiles.StartTempFileWatcher(); //watch temp directory on a diff schedule
                    _isTempCleanerRunning = true;
                }

                var dirName = TimelineBuilder.TimelineFilePath().DirectoryName;
                // now watch that file for changes
                if (_timelineWatcher == null && dirName != null) //you can change this to a bool if you want but checks if the object has been created
                {
                    _log.Trace("Timeline watcher starting and is null...");
                    _timelineWatcher = new FileSystemWatcher(dirName)
                    {
                        Filter = Path.GetFileName(TimelineBuilder.TimelineFilePath().Name)
                    };
                    _log.Trace($"watching {Path.GetFileName(TimelineBuilder.TimelineFilePath().Name)}");
                    _timelineWatcher.NotifyFilter = NotifyFilters.LastWrite;
                    _timelineWatcher.EnableRaisingEvents = true;
                    _timelineWatcher.Changed += OnChanged;
                }
                
                //load into an managing object
                //which passes the timeline commands to handlers
                //and creates a thread to execute instructions over that timeline
                if (_defaultTimeline.Status == Timeline.TimelineStatus.Run)
                {
                    RunEx(_defaultTimeline);
                }
                else
                {
                    if (MonitorThread != null)
                    {
                        MonitorThread.Abort();
                        MonitorThread = null;
                    }
                }
            }
            catch (Exception e)
            {
                _log.Error($"Orchestrator.Run exception: {e}");
            }
        }

        public void StopTimeline(Guid timelineId)
        {
            foreach (var threadJob in Program.ThreadJobs.Where(x => x.TimelineId == timelineId))
            {
                try
                {
                    threadJob.Thread.Abort(null);
                }
                catch (Exception e)
                {
                    _log.Debug(e);
                }

                try
                {
                    threadJob.Thread.Join();
                }
                catch (Exception e)
                {
                    _log.Debug(e);
                }
            }
        }

        public void Stop()
        {
            foreach (var threadJob in Program.ThreadJobs)
            {
                try
                {
                    threadJob.Thread.Abort(null);
                }
                catch (Exception e)
                {
                    _log.Debug(e);
                }

                try
                {
                    threadJob.Thread.Join();
                }
                catch (Exception e)
                {
                    _log.Debug(e);
                }
            }
        }

        private void RunEx(Timeline timeline)
        {
            WhatsInstalled();

            foreach (var handler in timeline.TimeLineHandlers)
            {
                ThreadLaunch(timeline, handler);
            }
        }

        public void RunCommand(Timeline timeline, TimelineHandler handler)
        {
            WhatsInstalled();
            ThreadLaunch(timeline, handler);
        }

        ///here lies technical debt
        //TODO clean up
        private void StartSafetyNet()
        {
            try
            {
                var t = new Thread(SafetyNet)
                {
                    IsBackground = true,
                    Name = "ghosts-safetynet"
                };
                t.Start(_defaultTimeline);
            }
            catch (Exception e)
            {
                _log.Error($"SafetyNet thread launch exception: {e}");
            }
        }

        ///here lies technical debt
        //TODO clean up
        // if supposed to be one excel running, and there is more than 2, then kill race condition
        private static void SafetyNet(object defaultTimeline)
        {
            var timeline = (Timeline) defaultTimeline;
            while (true)
            {
                try
                {
                    _log.Trace("SafetyNet loop beginning");

                    FileListing.FlushList();

                    var handlerCount = timeline.TimeLineHandlers.Count(o => o.HandlerType == HandlerType.Excel);
                    var pids = ProcessManager.GetPids(ProcessManager.ProcessNames.Excel).ToList();
                    if (pids.Count > handlerCount + 1)
                    {
                        _log.Trace($"SafetyNet excel handlers: {handlerCount} pids: {pids.Count} - killing");
                        ProcessManager.KillProcessAndChildrenByName(ProcessManager.ProcessNames.Excel);
                    }

                    handlerCount = timeline.TimeLineHandlers.Count(o => o.HandlerType == HandlerType.PowerPoint);
                    pids = ProcessManager.GetPids(ProcessManager.ProcessNames.PowerPoint).ToList();
                    if (pids.Count > handlerCount + 1)
                    {
                        _log.Trace($"SafetyNet powerpoint handlers: {handlerCount} pids: {pids.Count} - killing");
                        ProcessManager.KillProcessAndChildrenByName(ProcessManager.ProcessNames.PowerPoint);
                    }

                    handlerCount = timeline.TimeLineHandlers.Count(o => o.HandlerType == HandlerType.Word);
                    pids = ProcessManager.GetPids(ProcessManager.ProcessNames.Word).ToList();
                    if (pids.Count > handlerCount + 1)
                    {
                        _log.Trace($"SafetyNet word handlers: {handlerCount} pids: {pids.Count} - killing");
                        ProcessManager.KillProcessAndChildrenByName(ProcessManager.ProcessNames.Word);
                    }
                    _log.Trace("SafetyNet loop ending");
                }
                catch (Exception e)
                {
                    _log.Trace($"SafetyNet exception: {e}");
                }
                finally
                {
                    try
                    {
                        using (var proc = Process.GetCurrentProcess())
                        {
                            Console.WriteLine($"Minimizing footprint and memory. Current is {proc.PrivateMemorySize64 / (1024 * 1024)}...");
                            Program.MinimizeFootprint();
                            Program.MinimizeMemory();
                            Console.WriteLine($"Minimized footprint and memory.  Current is {proc.PrivateMemorySize64 / (1024 * 1024)}...");
                        }
                    }
                    catch (Exception e)
                    {
                        Console.WriteLine(e);
                    }


                    Thread.Sleep(300000); //clean up every 5 minutes
                }
            }
        }

        private void WhatsInstalled()
        {
            using (var regWord = Registry.ClassesRoot.OpenSubKey("Outlook.Application"))
            {
                if (regWord != null)
                {
                    IsOutlookInstalled = true;
                }

                _log.Trace($"Outlook is installed: {IsOutlookInstalled}");
            }

            using (var regWord = Registry.ClassesRoot.OpenSubKey("Word.Application"))
            {
                if (regWord != null)
                {
                    IsWordInstalled = true;
                }

                _log.Trace($"Word is installed: {IsWordInstalled}");
            }

            using (var regWord = Registry.ClassesRoot.OpenSubKey("Excel.Application"))
            {
                if (regWord != null)
                {
                    IsExcelInstalled = true;
                }

                _log.Trace($"Excel is installed: {IsExcelInstalled}");
            }

            using (var regWord = Registry.ClassesRoot.OpenSubKey("PowerPoint.Application"))
            {
                if (regWord != null)
                {
                    IsPowerPointInstalled = true;
                }

                _log.Trace($"PowerPoint is installed: {IsPowerPointInstalled}");
            }
        }

        private void ThreadLaunch(Timeline timeline, TimelineHandler handler)
        {
            try
            {
                _log.Trace($"Attempting new thread for: {handler.HandlerType}");

                Thread t = null;
                object _;
                switch (handler.HandlerType)
                {
                    case HandlerType.NpcSystem:
                        _ = new NpcSystem(timeline, handler);
                        break;
                    case HandlerType.Command:
                        t = new Thread(() =>
                        {
                            _ = new Cmd(handler);
                        });
                        break;
                    case HandlerType.Ssh:
                        t = new Thread(() =>
                        {
                            _ = new Ssh(handler);
                        });
                        break;
                    case HandlerType.Word:
                        _log.Trace("Launching thread for word");
                        if (IsWordInstalled)
                        {
                            var pids = ProcessManager.GetPids(ProcessManager.ProcessNames.Word).ToList();
                            if (pids.Count > timeline.TimeLineHandlers.Count(x => x.HandlerType == HandlerType.Word))
                                return;

                            t = new Thread(() =>
                            {
                                _ = new WordHandler(timeline, handler);
                            });
                        }
                        break;
                    case HandlerType.Excel:
                        _log.Trace("Launching thread for excel");
                        if (IsExcelInstalled)
                        {
                            var pids = ProcessManager.GetPids(ProcessManager.ProcessNames.Excel).ToList();
                            if (pids.Count > timeline.TimeLineHandlers.Count(x => x.HandlerType == HandlerType.Excel))
                                return;

                            t = new Thread(() =>
                            {
                                _ = new ExcelHandler(timeline, handler);
                            });
                        }
                        break;
                    case HandlerType.Clicks:
                        _log.Trace("Launching thread to handle clicks");
                        t = new Thread(() =>
                        {
                            _ = new Clicks(handler);
                        });
                        break;
                    case HandlerType.Reboot:
                        _log.Trace("Launching thread to handle reboot");
                        t = new Thread(() =>
                        {
                            _ = new Reboot(handler);
                        });
                        break;
                    case HandlerType.PowerPoint:
                        _log.Trace("Launching thread for powerpoint");
                        if (IsPowerPointInstalled)
                        {
                            var pids = ProcessManager.GetPids(ProcessManager.ProcessNames.PowerPoint).ToList();
                            if (pids.Count > timeline.TimeLineHandlers.Count(x => x.HandlerType == HandlerType.PowerPoint))
                                return;

                            t = new Thread(() =>
                            {
                                _ = new PowerPointHandler(timeline, handler);
                            });
                        }
                        break;
                    case HandlerType.Outlook:
                        _log.Trace("Launching thread for outlook - note we're not checking if outlook installed, just going for it");
                        t = new Thread(() =>
                        {
                            _ = new Outlook(handler);
                        });
                        break;
                    case HandlerType.Notepad:
                        //TODO
                        t = new Thread(() =>
                        {
                            _ = new Notepad(handler);
                        });
                        break;
                    case HandlerType.BrowserChrome:
                        t = new Thread(() =>
                        {
                            _ = new BrowserChrome(handler);
                        });
                        break;
                    case HandlerType.BrowserFirefox:
                        t = new Thread(() =>
                        {
                            _ = new BrowserFirefox(handler);
                        });
                        break;
                    case HandlerType.Watcher:
                        t = new Thread(() =>
                        {
                            _ = new Watcher(handler);
                        });
                        break;
                    case HandlerType.Print:
                        t = new Thread(() =>
                        {
                            _ = new Print(handler);
                        });
                        break;
                }

                if (t == null) return;

                t.IsBackground = true;
                t.Start();
                Program.ThreadJobs.Add(new ThreadJob
                {
                    TimelineId = timeline.Id,
                    Thread = t
                });
            }
            catch (Exception e)
            {
                _log.Error(e);
            }
        }
        
        private void OnChanged(object source, FileSystemEventArgs e)
        {
            try
            {
                _log.Trace($"FileWatcher event raised: {e.FullPath} {e.Name} {e.ChangeType}");

                // filewatcher throws two events, we only need 1
                var lastWriteTime = File.GetLastWriteTime(e.FullPath);
                if (lastWriteTime == _lastRead) return;

                _lastRead = lastWriteTime;
                _log.Trace("FileWatcher Processing: " + e.FullPath + " " + e.ChangeType);
                _log.Trace($"Reloading {MethodBase.GetCurrentMethod()?.DeclaringType}");

                _log.Trace("terminate existing tasks and rerun orchestrator");
                    
                try
                {
                    Stop();
                }
                catch (Exception exception)
                {
                    _log.Info(exception);
                }

                try
                {
                    StartupTasks.CleanupProcesses();
                }
                catch (Exception exception)
                {
                    _log.Info(exception);
                }

                Thread.Sleep(7500);

                try
                {
                    Run();
                }
                catch (Exception exception)
                {
                    _log.Info(exception);
                }
            }
            catch (Exception exc)
            {
                _log.Info(exc);
            }
        }
    }
}
