// Copyright 2017 Carnegie Mellon University. All Rights Reserved. See LICENSE.md file for terms.

using System;
using System.Text.RegularExpressions;
using Ghosts.Api.Models;
using Ghosts.Domain.Code;
using Microsoft.AspNetCore.Http;

namespace Ghosts.Api.Infrastructure
{
    public static class WebRequestReader
    {
        public static Machine GetMachine(HttpContext context)
        {
            try
            {
                var m = new Machine
                {
                    Name = context.Request.Headers["ghosts-name"],
                    FQDN = context.Request.Headers["ghosts-fqdn"],
                    Host = context.Request.Headers["ghosts-host"],
                    Domain = context.Request.Headers["ghosts-domain"],
                    ResolvedHost = context.Request.Headers["ghosts-resolvedhost"],
                    HostIp = context.Request.Headers["ghosts-ip"],
                    CurrentUsername = CheckIfBase64Encoded(context.Request.Headers["ghosts-user"]),
                    ClientVersion = context.Request.Headers["ghosts-version"],
                    IPAddress = context.Connection.RemoteIpAddress.ToString(),
                    StatusUp = Machine.UpDownStatus.Up
                };

                m.Name = m.Name.ToLower();
                m.FQDN = m.FQDN.ToLower();
                m.Host = m.Host.ToLower();
                m.ResolvedHost = m.ResolvedHost.ToLower();

                return m;
            }
            catch (Exception e)
            {
                Console.WriteLine(e);
                throw;
            }
        }

        private static string CheckIfBase64Encoded(string raw)
        {
            var reg = new Regex("^([A-Za-z0-9+/]{4})*([A-Za-z0-9+/]{3}=|[A-Za-z0-9+/]{2}==)?$");
            return reg.IsMatch(raw) ? Base64Encoder.Base64Decode(raw) : raw;
        }
    }
}