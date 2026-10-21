(() => {
 const card = document.getElementById("question-card");
 if (!card) return;
 const allQuestions = JSON.parse(card.dataset.questions);
 // Simple adaptive selection: order questions by section, then select a next difficulty
 // around the previous response. This is a teaching demo, not a calibrated CAT algorithm.
 let questions = [...allQuestions].sort(() => Math.random() - 0.5);
 const answers = {}; const events = [];
 let index = 0, seconds = 15*60, cameraStream = null, faceTimer = null, faceModelsReady = false, started = false, timer = null;
 const $ = id => document.getElementById(id);
 const sectionLabels = {quantitative:"Quantitative aptitude",logical:"Logical reasoning",verbal:"Verbal ability",technical:"Technical aptitude",data:"Data interpretation"};
 function record(type){ events.push({type, at:new Date().toISOString()}); }
 function updateGate(){ const ready=$("consent-check").checked && !!cameraStream && cameraStream.getVideoTracks().some(t=>t.readyState==="live"); $("begin-assessment").disabled=!ready || started; $("submit-test").disabled=!ready || !started; if(ready && !started) $("submit-status").textContent="Consent and webcam verified. Select Begin assessment to start the timer."; if(ready && started) $("submit-status").textContent="Assessment in progress."; }
 function render(){
   const q = questions[index];
   $("question-count").textContent = `Question ${index+1} of ${questions.length}`;
   $("progress-bar").style.width = `${((index+1)/questions.length)*100}%`;
   $("section-name").textContent = sectionLabels[q.section] || q.section;
   $("difficulty-label").textContent = `Level ${q.difficulty}`;
   $("question-text").textContent = q.text;
   $("options").innerHTML = "";
   q.options.forEach((opt, i) => {
     const label = document.createElement("label"); label.className = "option";
     const input = document.createElement("input"); input.type = "radio"; input.name = "answer"; input.value = String(i);
     input.checked = answers[q.id] === String(i);
     input.addEventListener("change", () => {
       const previous = answers[q.id]; answers[q.id] = String(i);
       // Adapt difficulty of the next unseen question based on current answer correctness.
       const correct = String(i) === String(q.answer);
       const next = questions.slice(index+1).find(x => x.difficulty === (correct ? Math.min(3, q.difficulty+1) : Math.max(1, q.difficulty-1)));
       if (next) { const pos = questions.indexOf(next); questions.splice(pos,1); questions.splice(index+1,0,next); }
     });
     const span = document.createElement("span"); span.textContent = opt;
     label.append(input, span); $("options").appendChild(label);
   });
   $("prev-btn").disabled = index === 0;
   $("next-btn").textContent = index === questions.length-1 ? "Review complete" : "Next question →";
 }
 $("prev-btn").addEventListener("click", () => {if(index>0){index--;render();}});
 $("next-btn").addEventListener("click", () => {if(index<questions.length-1){index++;render();} else {$("submit-status").textContent="You are at the final question. Submit when ready."; }});
 function startTimer(){
   if(timer) return;
   timer = setInterval(() => {
     seconds--; const m = Math.floor(seconds/60), s = seconds%60;
     $("timer").textContent = `${String(m).padStart(2,"0")}:${String(s).padStart(2,"0")}`;
     if(seconds<=0){clearInterval(timer); timer=null; if($("consent-check").checked && cameraStream && cameraStream.getVideoTracks().some(t=>t.readyState==="live")) submit(); else $("submit-status").textContent="Time ended, but consent and a working camera are required to submit.";}
   },1000);
 }
 $("begin-assessment").addEventListener("click",()=>{
   if(!$("consent-check").checked || !cameraStream || !cameraStream.getVideoTracks().some(t=>t.readyState==="live")){updateGate();return;}
   started=true; $("question-card").hidden=false; $("question-count").textContent=`Question 1 of ${questions.length}`; startTimer(); updateGate(); render();
 });
 document.addEventListener("visibilitychange",()=>{if(document.hidden)record("tab_hidden");});
 document.addEventListener("fullscreenchange",()=>{if(!document.fullscreenElement)record("fullscreen_exit");});
 $("camera-start").addEventListener("click", startCamera);
 $("consent-check").addEventListener("change", updateGate);
 $("camera-check").addEventListener("change", () => { if($("camera-check").checked && !cameraStream) startCamera(); else updateGate(); });
 async function startCamera(){
   try {
     cameraStream = await navigator.mediaDevices.getUserMedia({video:{facingMode:"user"},audio:false});
     $("webcam").srcObject = cameraStream; $("camera-check").checked = true; $("camera-status").textContent = "Camera enabled. Checking face presence locally."; updateGate();
     if (window.faceapi) {
       try {
         const modelUrl = "https://justadudewhohacks.github.io/face-api.js/models";
         await faceapi.nets.tinyFaceDetector.loadFromUri(modelUrl); faceModelsReady=true;
         faceTimer=setInterval(async()=>{
           try {
             const detections=await faceapi.detectAllFaces($("webcam"),new faceapi.TinyFaceDetectorOptions());
             if(detections.length===0) record("face_not_detected");
             if(detections.length>1) record("multiple_faces_detected");
             $("camera-status").textContent = detections.length===0 ? "No face detected — check camera position." : detections.length>1 ? "More than one face detected — review signal." : "Face presence detected locally.";
           } catch(e) {}
         },5000);
       } catch(e) { $("camera-status").textContent="Camera enabled; face model unavailable. Other test features remain available."; }
     } else { $("camera-status").textContent="Camera enabled; face model library unavailable. Other test features remain available."; }
   } catch(e) {
     record("camera_unavailable"); cameraStream=null; $("camera-check").checked=false; $("camera-status").textContent="Camera unavailable or permission denied. Submission remains locked until the camera works."; updateGate();
   }
 }
 async function submit(){
   $("submit-test").disabled=true; $("submit-status").textContent="Scoring your assessment…";
   if(faceTimer)clearInterval(faceTimer);
   const cameraEnabled=!!cameraStream && cameraStream.getVideoTracks().some(t=>t.readyState==="live");
   const payload={answers,events,proctoringConsent:$("consent-check").checked,cameraEnabled};
   try{
     const res=await fetch("/api/submit-assessment",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(payload)});
     const data=await res.json();
     if(!res.ok)throw new Error(data.error||"Could not submit assessment.");
     if(cameraStream)cameraStream.getTracks().forEach(t=>t.stop());
     // The report endpoint is populated by the server; ID is user-owned.
     window.location.href = data.assessment_id ? `/results/${data.assessment_id}` : `/dashboard`;
   }catch(e){$("submit-status").textContent=e.message;$("submit-test").disabled=false;}
 }
 $("submit-test").addEventListener("click",()=>{
   if(!started){$("submit-status").textContent="Complete consent and webcam checks, then begin the assessment.";return;}
   if(!$("consent-check").checked){$("submit-status").textContent="Please confirm the proctoring/privacy notice before submitting.";return;}
   if(!confirm("Submit your assessment now?"))return; submit();
 });
 render(); updateGate();
})();
