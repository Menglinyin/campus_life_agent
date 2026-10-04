class CampusRecorderProcessor extends AudioWorkletProcessor {
  constructor() { super(); this.active=true; this.port.onmessage=event=>{if(event.data==='stop'){this.active=false;this.port.postMessage({stopped:true});}}; }
  process(inputs) {
    const channels=inputs[0];
    if(this.active&&channels?.length){const mono=new Float32Array(channels[0].length);for(const channel of channels)for(let i=0;i<mono.length;i++)mono[i]+=channel[i]/channels.length;this.port.postMessage({samples:mono},[mono.buffer]);}
    return this.active;
  }
}
registerProcessor('campus-recorder',CampusRecorderProcessor);
