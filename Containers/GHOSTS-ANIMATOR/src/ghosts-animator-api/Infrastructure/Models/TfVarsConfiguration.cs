// Copyright 2020 Carnegie Mellon University. All Rights Reserved. See LICENSE.md file for terms.

using System;
using System.Collections.Generic;

namespace Ghosts.Animator.Api.Infrastructure.Models;

public class TfVarsConfiguration
{
    public string Campaign { get; set; }
    public string Enclave { get; set; }
    public string Team { get; set; }
    public string IpAddressHigh { get; set; }
    public string IpAddressLow { get; set; }
    public string Gateway { get; set; }
    public string Mask { get; set; }

    public IList<string> GetIpPool()
    {
        var pool = new List<string>();

        var lowArr = this.IpAddressLow.Split(".");
        var highArr = this.IpAddressHigh.Split(".");

        var low = Convert.ToInt32(lowArr[lowArr.GetUpperBound(0)]);
        var high = Convert.ToInt32(highArr[highArr.GetUpperBound(0)]);
            
        for (var i = low; i < high; i++)
        {
            pool.Add(ReplaceLastOccurrence(this.IpAddressLow, low.ToString(), i.ToString()));
        }
        pool.Add(this.IpAddressHigh);
        return pool;
    }
        
    private static string ReplaceLastOccurrence(string Source, string Find, string Replace)
    {
        var place = Source.LastIndexOf(Find, StringComparison.CurrentCultureIgnoreCase);

        if(place == -1)
            return Source;

        var result = Source.Remove(place, Find.Length).Insert(place, Replace);
        return result;
    }
}