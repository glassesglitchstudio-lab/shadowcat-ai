/* Shadowcat Global Skill Library - executable skills (fonksiyon tabanlı) */
window.SKILL_LIBRARY = [
{
    id:'hesapla', name:'Hesaplama', icon:'calc',
    desc:'Matematiksel ifadeleri ve yüzdeleri çözer',
    example:'150 ile 30 topla',
    keywords:['hesapla','kaç eder','topla','çıkar','çarp','böl','yüzde'],
    match:/\d\s*[\+\-\*xX%\/]\s*\d|%\s*\d/,
    run:function(t){
        var txt=t.toLowerCase().replace(/,/g,'.');
        var op=null;
        if(/topla|artı/.test(txt)||txt.indexOf('+')>=0) op='+';
        else if(/çıkar|eksi/.test(txt)||txt.indexOf('-')>=0) op='-';
        else if(/çarp|çarpı/.test(txt)||txt.indexOf('*')>=0||/[xX]/.test(txt)) op='*';
        else if(/böl|bölü/.test(txt)||txt.indexOf('/')>=0) op='/';
        else if(/yüzde|%/.test(txt)) op='%';
        if(!op) return {ok:false};
        var nums=(txt.match(/\d+(?:\.\d+)?/g)||[]).map(parseFloat).slice(0,2);
        if(nums.length<2) return {ok:false};
        var a=nums[0],b=nums[1],val;
        if(op==='+') val=a+b;
        else if(op==='-') val=a-b;
        else if(op==='*') val=a*b;
        else if(op==='/') val=b===0?NaN:a/b;
        else val=a*b/100;
        if(isNaN(val)) return {ok:false};
        var opTxt=op==='+'?'+':op==='-'?'-':op==='*'?'x':op==='/'?'/':'%';
        return {ok:true,text:a+' '+opTxt+' '+b+' = **'+(Math.round(val*1e6)/1e6)+'**'};
    }
},
{
    id:'birim-cevir', name:'Birim Çevirme', icon:'ruler',
    desc:'km/mil, kg/lb, m/ft, litre/galon, C/F dönüşümü',
    example:'5 km kaç mil',
    keywords:['çevir','kaç mil','kaç km','kaç pound','kaç libre','kaç feet','kaç galon','fahrenheit','celsius'],
    run:function(t){
        var txt=t.toLowerCase();
        var m=txt.match(/(\d+(?:\.\d+)?)\s*(km|mil|kg|pound|libre|m|ft|feet|l|lt|litre|galon|c|f)/);
        if(!m) return {ok:false};
        var v=parseFloat(m[1]),u=m[2],out=null,outU='';
        if(u==='km'){out=v/1.609;outU='mil';}
        else if(u==='mil'){out=v*1.609;outU='km';}
        else if(u==='kg'){out=v*2.205;outU='lb';}
        else if(u==='pound'||u==='libre'){out=v/2.205;outU='kg';}
        else if(u==='m'){out=v*3.281;outU='ft';}
        else if(u==='ft'||u==='feet'){out=v/3.281;outU='m';}
        else if(u==='l'||u==='lt'||u==='litre'){out=v/3.785;outU='galon';}
        else if(u==='galon'){out=v*3.785;outU='litre';}
        else if(u==='c'){out=v*9/5+32;outU='F';}
        else if(u==='f'){out=(v-32)*5/9;outU='C';}
        if(out===null) return {ok:false};
        return {ok:true,text:v+' '+u+' = **'+(Math.round(out*1000)/1000)+' '+outU+'**'};
    }
},
{
    id:'sifre-uretici', name:'Şifre Üretici', icon:'key',
    desc:'Güçlü rastgele şifre üretir',
    example:'şifre üret 16',
    keywords:['şifre üret','şifre oluştur','password üret'],
    run:function(t){
        var m=t.match(/\d+/);
        var n=Math.min(32,Math.max(8,m?parseInt(m[0]):12));
        var chars='ABCDEFGHJKLMNPQRSTUVWXYZabcdefghjkmnpqrstuvwxyz23456789!@#$%&*';
        var p='';
        for(var i=0;i<n;i++) p+=chars.charAt(Math.floor(Math.random()*chars.length));
        return {ok:true,text:'**'+p+'**\n\n`'+n+'` karakterli güçlü şifre üretildi.'};
    }
},
{
    id:'kelime-sayaci', name:'Kelime Sayacı', icon:'digits',
    desc:'Metnin kelime, harf ve cümle sayısını hesaplar',
    example:'kelime say: merhaba dünya',
    keywords:['kelime say','harf say','kelime sayacı'],
    run:function(t){
        var txt=t.replace(/^[^:(]*[:(]\s*/,'').trim();
        if(txt.length<3) return {ok:false};
        var words=txt.split(/\s+/).filter(Boolean);
        var letters=txt.replace(/\s+/g,'').length;
        var sentences=(txt.match(/[.!?…]+/g)||[]).length||1;
        return {ok:true,text:'Metin: "'+txt.slice(0,60)+(txt.length>60?'…':'')+'"\n\n- Kelime: **'+words.length+'**\n- Harf: **'+letters+'**\n- Cümle: **'+sentences+'**'};
    }
},
{
    id:'json-duzenleyici', name:'JSON Düzenleyici', icon:'box',
    desc:'Tek satır veya bozuk JSON u sıralar ve doğrular',
    example:'json düzenle: {"a":1,"b":[2,3]}',
    keywords:['json düzenle','json biçimle','json formatla'],
    run:function(t){
        var i=t.indexOf('{');
        if(i<0) return {ok:false};
        try{
            var obj=JSON.parse(t.slice(i));
            return {ok:true,text:'```json\n'+JSON.stringify(obj,null,2)+'\n```'};
        }catch(e){
            return {ok:true,text:'JSON geçersiz: '+e.message};
        }
    }
},
{
    id:'yas-hesapla', name:'Yaş Hesaplama', icon:'cake',
    desc:'Doğum yılından yaş hesaplar',
    example:'1990 doğumluyum kaç yaşındayım',
    keywords:['doğum','doğdum','yaşım','kaç yaşında','yaş hesapla'],
    run:function(t){
        var m=t.match(/(19|20)\d{2}/);
        if(!m) return {ok:false};
        var y=parseInt(m[0]);
        if(y<1900||y>2100) return {ok:false};
        var now=new Date().getFullYear();
        var age=now-y;
        return {ok:true,text:'**'+y+'** doğumlu — bugün **'+now+'** itibarıyla **'+age+' yaşında**.'};
    }
},
{
    id:'tarih-farki', name:'Tarih Farkı', icon:'calendar',
    desc:'İki tarih arasındaki gün sayısını hesaplar',
    example:'01.01.2026 ile 01.06.2026 arası kaç gün',
    keywords:['kaç gün','gün kaldı','tarih farkı','arası kaç gün'],
    run:function(t){
        function parse(d){
            var p=d.split(/[./-]/);
            var day=+p[0],mon=+p[1],yr=+p[2];
            if(yr<100) yr+=2000;
            return new Date(yr,mon-1,day);
        }
        var ds=(t.match(/\d{1,2}[./-]\d{1,2}[./-]\d{2,4}/g)||[]);
        if(ds.length===0) return {ok:false};
        var a=parse(ds[0]),b=ds.length>1?parse(ds[1]):new Date();
        var days=Math.abs(Math.round((b-a)/(86400000)));
        if(ds.length===1) return {ok:true,text:'**'+ds[0]+'** tarihine **'+days+' gün** kaldı.'};
        return {ok:true,text:ds[0]+' ile '+ds[1]+' arasında **'+days+' gün** var.'};
    }
},
{
    id:'asal-kontrol', name:'Asal Sayı', icon:'digits',
    desc:'Sayının asal olup olmadığını kontrol eder',
    example:'17 asal mı',
    keywords:['asal mı','asal kontrol'],
    run:function(t){
        var m=t.match(/\d+/);
        if(!m) return {ok:false};
        var n=parseInt(m[0]);
        if(n<2) return {ok:true,text:n+' asal değil.'};
        var prime=true;
        for(var i=2;i*i<=n;i++) if(n%i===0){prime=false;break;}
        return {ok:true,text:'**'+n+'** '+(prime?'asal bir sayıdır (evet)':'asal değildir (hayır)')};
    }
},
{
    id:'fibonacci', name:'Fibonacci', icon:'spiral',
    desc:'Fibonacci dizisini üretir',
    example:'fibonacci 12',
    keywords:['fibonacci'],
    run:function(t){
        var m=t.match(/\d+/);
        var n=Math.min(40,m?parseInt(m[0]):10);
        var seq=[0,1];
        for(var i=2;i<n;i++) seq.push(seq[i-1]+seq[i-2]);
        return {ok:true,text:'İlk **'+n+'** Fibonacci terimi:\n\n'+seq.join(', ')};
    }
},
{
    id:'faktoriyel', name:'Faktoriyel', icon:'exclaim',
    desc:'n! hesaplar',
    example:'faktoriyel 6',
    keywords:['faktoriyel','faktöriyel'],
    run:function(t){
        var m=t.match(/\d+/);
        if(!m) return {ok:false};
        var n=parseInt(m[0]);
        if(n>170) return {ok:false};
        var r=1;
        for(var i=2;i<=n;i++) r*=i;
        return {ok:true,text:n+'! = **'+r.toLocaleString('tr-TR')+'**'};
    }
},
{
    id:'rastgele-sayi', name:'Rastgele Sayı', icon:'dice',
    desc:'Belirtilen aralıkta rastgele sayı üretir',
    example:'1 ile 100 arası rastgele',
    keywords:['rastgele','random sayı','zar at'],
    run:function(t){
        var nums=(t.match(/\d+/g)||[]).map(parseFloat);
        var lo=nums.length?Math.min(nums[0],nums[nums.length-1]):1;
        var hi=nums.length>1?Math.max(nums[0],nums[nums.length-1]):100;
        var v=Math.floor(Math.random()*(hi-lo+1))+lo;
        return {ok:true,text:'(zar) **'+lo+' - '+hi+'** aralığında: **'+v+'**'};
    }
},
{
    id:'ters-metin', name:'Ters Çevirici', icon:'refresh',
    desc:'Metni tersine çevirir',
    example:'ters çevir: merhaba',
    keywords:['ters çevir','tersine çevir','reverse'],
    run:function(t){
        var txt=t.replace(/^[^:(]*[:(]\s*/,'').trim();
        if(txt.length<2) return {ok:false};
        return {ok:true,text:'"'+txt.split('').reverse().join('')+'"'};
    }
},
{
    id:'buyuk-harf', name:'Büyük/Küçük Harf', icon:'letters',
    desc:'Metni büyük veya küçük harfe çevirir',
    example:'büyük harf yap: merhaba',
    keywords:['büyük harf','küçük harf','uppercase','lowercase'],
    run:function(t){
        var txt=t.replace(/^[^:(]*[:(]\s*/,'').trim();
        if(txt.length<2) return {ok:false};
        if(/küçük|kucuk|lower/.test(t)) return {ok:true,text:txt.toLowerCase()};
        return {ok:true,text:txt.toUpperCase()};
    }
},
{
    id:'kisaltma', name:'Metin Kısaltma', icon:'scissors',
    desc:'Uzun metni istenen karakter sayısına kısaltır',
    example:'kısalt 50: çok uzun bir metin...',
    keywords:['kısalt','özetle','shorten'],
    run:function(t){
        var txt=t.replace(/^[^:(]*[:(]\s*/,'').trim();
        var m=t.match(/\d+/);
        var n=Math.min(500,m?parseInt(m[0]):100);
        if(txt.length<2) return {ok:false};
        if(txt.length<=n) return {ok:true,text:txt};
        return {ok:true,text:txt.slice(0,n)+'…\n\n_(**'+txt.length+'** karakter -> **'+n+'** karakter)_'};
    }
},
{
    id:'kdv-hesapla', name:'KDV Hesaplama', icon:'receipt',
    desc:'KDV tutarı ve genel toplamı hesaplar',
    example:'200 tl %20 kdv',
    keywords:['kdv','vergi'],
    run:function(t){
        var nums=(t.match(/\d+(?:[.,]\d+)?/g)||[]).map(function(x){return parseFloat(x.replace(',','.'))});
        if(nums.length<2) return {ok:false};
        var amt=nums[0],pct=nums[1];
        var tax=Math.round(amt*pct/100*100)/100;
        return {ok:true,text:amt+' TL, %'+pct+' KDV:\n\n- KDV tutarı: **'+tax+' TL**\n- Genel toplam: **'+(amt+tax)+' TL**'};
    }
},
{
    id:'quiz', name:'Mini Quiz', icon:'question',
    desc:'Rastgele bilgi sorusu sorar ve cevabını verir',
    example:'quiz yap',
    keywords:['quiz','soru sor','bilgi yarışması'],
    run:function(){
        var qs=[
            {q:'Hangi gezegen Güneş e en yakındır?',a:'Merkür'},
            {q:'Python un yaratıcısı kimdir?',a:'Guido van Rossum'},
            {q:'HTML açılımı nedir?',a:'HyperText Markup Language'},
            {q:'Bir baytta kaç bit vardır?',a:'8'},
            {q:'HTTP hangi portu kullanır?',a:'80'},
            {q:'Türkiye nin başkenti neresidir?',a:'Ankara'}
        ];
        var q=qs[Math.floor(Math.random()*qs.length)];
        return {ok:true,text:'**Soru:** '+q.q+'\n\n**Cevap:** '+q.a};
    }
},
{
    id:'zar-at', name:'Zar Atma', icon:'dice',
    desc:'Sanal zar atar (1-6)',
    example:'zar at',
    keywords:['zar at','zarları at'],
    run:function(){ return {ok:true,text:'(zar) **'+(Math.floor(Math.random()*6)+1)+'** geldi!'}; }
},
{
    id:'yazi-tura', name:'Yazı Tura', icon:'coin',
    desc:'Sanal para atar',
    example:'yazı tura at',
    keywords:['yazı tura','para at'],
    run:function(){ return {ok:true,text:'(yazı tura) **'+(Math.random()<0.5?'YAZI':'TURA')+'**'}; }
},
{
    id:'ussu-al', name:'Üs Alma', icon:'calc',
    desc:'Üslü sayı, kare ve küp hesaplar',
    example:'2 üssü 10',
    keywords:['üssü','üzeri','üstü','kare al','küp al','karesi'],
    run:function(t){
        var m=t.toLowerCase().match(/(\d+)\s*(?:\^|üssü|üzeri|üstü)\s*(\d+)/);
        if(m) return {ok:true,text:m[1]+' üssü '+m[2]+' = **'+Math.pow(+m[1],+m[2])+'**'};
        m=t.toLowerCase().match(/kare\s*al\s*(\d+)/);
        if(m) return {ok:true,text:m[1]+'² = **'+(m[1]*m[1])+'**'};
        m=t.toLowerCase().match(/küp\s*al\s*(\d+)/);
        if(m) return {ok:true,text:m[1]+'³ = **'+(m[1]*m[1]*m[1])+'**'};
        return {ok:false};
    }
},
{
    id:'karekok', name:'Karekök', icon:'sprout',
    desc:'Karekök hesaplar',
    example:'karekök 144',
    keywords:['karekök','kök al'],
    run:function(t){
        var m=t.match(/\d+/);
        if(!m) return {ok:false};
        var v=Math.sqrt(+m[0]);
        if(!isFinite(v)) return {ok:false};
        return {ok:true,text:'√'+m[0]+' = **'+(Math.round(v*1e6)/1e6)+'**'};
    }
},
{
    id:'ortalama', name:'Ortalama', icon:'chart',
    desc:'Sayıların ortalamasını hesaplar',
    example:'ortalama: 5,7,9',
    keywords:['ortalama','ortalaması'],
    run:function(t){
        var nums=(t.match(/\d+(?:[.,]\d+)?/g)||[]).map(function(x){return parseFloat(x.replace(',','.'))});
        if(nums.length<2) return {ok:false};
        var avg=nums.reduce(function(a,b){return a+b},0)/nums.length;
        return {ok:true,text:nums.join(', ')+' ortalaması = **'+(Math.round(avg*100)/100)+'**'};
    }
},
{
    id:'min-max', name:'Min / Maks', icon:'trend',
    desc:'Sayıların en büyüğünü veya en küçüğünü bulur',
    example:'en büyük: 5,12,7',
    keywords:['en büyük','en küçük','en yüksek','en düşük'],
    run:function(t){
        var nums=(t.match(/\d+(?:[.,]\d+)?/g)||[]).map(function(x){return parseFloat(x.replace(',','.'))});
        if(nums.length<2) return {ok:false};
        var big=Math.max.apply(null,nums), small=Math.min.apply(null,nums);
        var kind=/küçük|kucuk|düşük|dusuk/.test(t)?'En küçük':'En büyük';
        return {ok:true,text:kind+': **'+(kind==='En küçük'?small:big)+'**\n\nTüm değerler: '+nums.join(', ')};
    }
},
{
    id:'indirim', name:'İndirim Hesaplama', icon:'tag',
    desc:'İndirimli fiyatı hesaplar',
    example:'100 tl %20 indirim',
    keywords:['indirim'],
    run:function(t){
        var nums=(t.match(/\d+(?:[.,]\d+)?/g)||[]).map(function(x){return parseFloat(x.replace(',','.'))});
        if(nums.length<2) return {ok:false};
        var dis=nums[0]*nums[1]/100;
        return {ok:true,text:nums[0]+' TL, %'+nums[1]+' indirim:\n\n- İndirim: **'+dis+' TL**\n- Ödenecek: **'+(nums[0]-dis)+' TL**'};
    }
},
{
    id:'bahsis', name:'Bahşiş Hesaplama', icon:'money',
    desc:'Bahşiş ve toplam ödemeyi hesaplar',
    example:'500 tl %10 bahşiş',
    keywords:['bahşiş','bahsis'],
    run:function(t){
        var nums=(t.match(/\d+(?:[.,]\d+)?/g)||[]).map(function(x){return parseFloat(x.replace(',','.'))});
        if(nums.length<2) return {ok:false};
        var tip=nums[0]*nums[1]/100;
        return {ok:true,text:nums[0]+' TL, %'+nums[1]+' bahşiş:\n\n- Bahşiş: **'+tip+' TL**\n- Toplam: **'+(nums[0]+tip)+' TL**'};
    }
},
{
    id:'faiz', name:'Faiz Hesaplama', icon:'bank',
    desc:'Yıllık basit faizi hesaplar',
    example:'10000 tl %10 faiz',
    keywords:['faiz'],
    run:function(t){
        var nums=(t.match(/\d+(?:[.,]\d+)?/g)||[]).map(function(x){return parseFloat(x.replace(',','.'))});
        if(nums.length<2) return {ok:false};
        var interest=nums[0]*nums[1]/100;
        return {ok:true,text:nums[0]+' TL, %'+nums[1]+' yıllık faiz:\n\n- Yıllık faiz: **'+interest+' TL**\n- Toplam: **'+(nums[0]+interest)+' TL**'};
    }
},
{
    id:'doviz', name:'Döviz Çevirme', icon:'exchange',
    desc:'USD/EUR/GBP <-> TL çevirir (demo kur)',
    example:'100 usd kaç tl',
    keywords:['usd','eur','gbp','dolar','euro','sterlin'],
    run:function(t){
        var m=t.match(/(\d+(?:[.,]\d+)?)\s*(usd|eur|gbp|dolar|euro|sterlin)/i);
        if(!m) return {ok:false};
        var v=parseFloat(m[1].replace(',','.')),u=m[2].toLowerCase();
        var rates={usd:38,dolar:38,eur:41,euro:41,gbp:48,sterlin:48};
        var sym=u==='usd'||u==='dolar'?'USD':u==='eur'||u==='euro'?'EUR':'GBP';
        return {ok:true,text:v+' '+sym+' = **'+(Math.round(v*rates[u]*100)/100)+' TL** (demo kur)'};
    }
},
{
    id:'bmi', name:'BMI Hesaplama', icon:'scale',
    desc:'Vücut kitle indeksi hesaplar',
    example:'175 cm 70 kg',
    keywords:['bmi','vücut kitle','kitle indeksi'],
    run:function(t){
        var mc=t.match(/(\d+(?:[.,]\d+)?)\s*cm/);
        var mk=t.match(/(\d+(?:[.,]\d+)?)\s*kg/);
        if(!mc||!mk) return {ok:false};
        var h=+mc[1].replace(',','.'),w=+mk[1].replace(',','.');
        var bmi=w/Math.pow(h/100,2);
        var cat=bmi<18.5?'zayıf':bmi<25?'normal':bmi<30?'fazla kilolu':'obez';
        return {ok:true,text:'Boy: '+h+' cm, Kilo: '+w+' kg\n\nBMI: **'+Math.round(bmi*10)/10+'** -> **'+cat+'**'};
    }
},
{
    id:'su-ihtiyaci', name:'Su İhtiyacı', icon:'drop',
    desc:'Günlük su ihtiyacını hesaplar',
    example:'70 kg su ihtiyacı',
    keywords:['su ihtiyacı','su ihtiyacım','kaç litre su'],
    run:function(t){
        var m=t.match(/\d+/);
        if(!m) return {ok:false};
        var w=+m[0],liters=Math.round(w*0.033*100)/100;
        return {ok:true,text:w+' kg için günlük önerilen su: **'+liters+' litre** (≈'+Math.round(liters/0.2)+' bardak)'};
    }
},
{
    id:'baskent', name:'Başkent Bilgisi', icon:'columns',
    desc:'Ülkelerin başkentlerini söyler',
    example:'fransa nın başkenti',
    keywords:['başkent','başkenti'],
    run:function(t){
        var map={fransa:'Paris',almanya:'Berlin',italya:'Roma',ispanya:'Madrid',japonya:'Tokyo',çin:'Pekin',ingiltere:'Londra',abd:'Washington',amerika:'Washington',rusya:'Moskova',türkiye:'Ankara',turkiye:'Ankara',mısır:'Kahire',hindistan:'Yeni Delhi',brezilya:'Brasilia',kanada:'Ottawa',avustralya:'Canberra',yunanistan:'Atina',hollanda:'Amsterdam',isviçre:'Bern',portekiz:'Lizbon',isveç:'Stokholm'};
        for(var k in map) if(t.toLowerCase().includes(k)) return {ok:true,text:'**'+k.charAt(0).toUpperCase()+k.slice(1)+'** — başkent: **'+map[k]+'**'};
        return {ok:false};
    }
},
{
    id:'telefon-kodu', name:'Ülke Kodu', icon:'phone',
    desc:'Telefon ülke kodlarını söyler',
    example:'+33 hangi ülke',
    keywords:['ülke kodu','telefon kodu'],
    run:function(t){
        var map={'90':'Türkiye (TR)','1':'ABD (US)','33':'Fransa (FR)','49':'Almanya (DE)','44':'İngiltere (UK)','7':'Rusya (RU)','86':'Çin (CN)','81':'Japonya (JP)','30':'Yunanistan (GR)','39':'İtalya (IT)'};
        var m=t.match(/\+?(\d{1,3})/);
        if(!m) return {ok:false};
        var code=m[1];
        if(map[code]) return {ok:true,text:'+'+code+' -> **'+map[code]+'**'};
        return {ok:true,text:'+'+code+' kodu veritabanında yok (demo — 10 ülke yüklü)'};
    }
},
{
    id:'binary', name:'Binary Çevirme', icon:'0',
    desc:'Sayıyı ikilik (binary) sisteme çevirir',
    example:'5 binary',
    keywords:['binary','ikili sistem','2 taban'],
    run:function(t){
        var m=t.match(/\d+/);
        if(!m) return {ok:false};
        return {ok:true,text:m[0]+' (10 taban) = **'+(+m[0]).toString(2)+'** (2 taban)'};
    }
},
{
    id:'hex-cevir', name:'Hex Çevirme', icon:'letter-a',
    desc:'Sayıyı onaltılık (hex) sisteme çevirir',
    example:'255 hex',
    keywords:['hex','16 taban'],
    run:function(t){
        var m=t.match(/\d+/);
        if(!m) return {ok:false};
        return {ok:true,text:m[0]+' (10 taban) = **0x'+(+m[0]).toString(16).toUpperCase()+'** (16 taban)'};
    }
},
{
    id:'base64', name:'Base64 Kodlama', icon:'lock',
    desc:'Metni Base64 e çevirir',
    example:'base64: merhaba',
    keywords:['base64'],
    run:function(t){
        var txt=t.replace(/^[^:(]*[:(]\s*/,'').trim();
        if(txt.length<2) return {ok:false};
        return {ok:true,text:'**'+btoa(unescape(encodeURIComponent(txt)))+'**'};
    }
},
{
    id:'url-encode', name:'URL Kodlama', icon:'link',
    desc:'Metni URL güvenli biçime çevirir',
    example:'url: merhaba dünya',
    keywords:['url kodla','url encode'],
    run:function(t){
        var txt=t.replace(/^[^:(]*[:(]\s*/,'').trim();
        if(txt.length<2) return {ok:false};
        return {ok:true,text:encodeURIComponent(txt)};
    }
},
{
    id:'renk-donustur', name:'Renk Çevirici', icon:'palette',
    desc:'HEX <-> RGB renk dönüşümü',
    example:'#ff0000 rgb',
    keywords:['rgb','hex renk','renk çevir'],
    run:function(t){
        var m=t.match(/#[0-9a-fA-F]{6}/);
        if(m){
            var h=m[0].slice(1);
            return {ok:true,text:m[0]+' = **rgb('+parseInt(h.slice(0,2),16)+', '+parseInt(h.slice(2,4),16)+', '+parseInt(h.slice(4,6),16)+')**'};
        }
        var nums=(t.match(/\d{1,3}/g)||[]).map(parseInt).slice(0,3);
        if(nums.length===3){
            var hex='#'+nums.map(function(n){return ('0'+Math.min(255,Math.max(0,n)).toString(16)).slice(-2)}).join('');
            return {ok:true,text:'rgb('+nums.join(', ')+') = **'+hex.toUpperCase()+'**'};
        }
        return {ok:false};
    }
},
{
    id:'palindrom', name:'Palindrom Kontrol', icon:'sync',
    desc:'Metnin palindrom olup olmadığını söyler',
    example:'palindrom: kasım',
    keywords:['palindrom'],
    run:function(t){
        var orig=t.replace(/^[^:(]*[:(]\s*/,'').trim();
        var txt=orig.toLowerCase().replace(/[^a-zçğıöşü0-9]/g,'');
        if(txt.length<2) return {ok:false};
        return {ok:true,text:'"'+orig+'" '+(txt===txt.split('').reverse().join('')?'**palindrom** (evet)':'palindrom **değil** (hayır)')};
    }
},
{
    id:'sesli-harf', name:'Sesli Harf Sayacı', icon:'volume',
    desc:'Metindeki sesli ve sessiz harf sayısını bulur',
    example:'sesli harf: merhaba',
    keywords:['sesli harf','ünlü harf'],
    run:function(t){
        var txt=t.replace(/^[^:(]*[:(]\s*/,'').trim().toLowerCase();
        if(txt.length<2) return {ok:false};
        var v=(txt.match(/[aeiouöüı]/g)||[]).length;
        var c=(txt.match(/[bcçdfgğhjklmnprsştvyz]/g)||[]).length;
        return {ok:true,text:'"'+txt+'"\n\n- Sesli: **'+v+'**\n- Sessiz: **'+c+'**'};
    }
},
{
    id:'ilk-harf', name:'Baş Harfler', icon:'abc',
    desc:'Kelimelerin baş harflerini alır',
    example:'baş harfler: mustafa kemal',
    keywords:['baş harf','baş harfler','ilk harfleri'],
    run:function(t){
        var txt=t.replace(/^[^:(]*[:(]\s*/,'').trim();
        if(txt.length<2) return {ok:false};
        var init=txt.split(/\s+/).filter(Boolean).map(function(w){return w.charAt(0)}).join('');
        return {ok:true,text:'"'+txt+'" -> **'+init.toUpperCase()+'**'};
    }
},
{
    id:'alfabe-sirala', name:'Alfabetik Sıralama', icon:'lowercase',
    desc:'Kelimeleri alfabetik sıralar',
    example:'sırala: muz elma kiraz',
    keywords:['sırala','alfabetik sırala'],
    run:function(t){
        var txt=t.replace(/^[^:(]*[:(]\s*/,'').trim();
        var words=txt.split(/[\s,;]+/).filter(Boolean);
        if(words.length<2) return {ok:false};
        return {ok:true,text:words.slice().sort(function(a,b){return a.localeCompare(b,'tr')}).join(', ')};
    }
},
{
    id:'hangi-gun', name:'Hangi Gün', icon:'calendar2',
    desc:'Bir tarihin hangi güne denk geldiğini söyler',
    example:'01.01.2026 hangi gün',
    keywords:['hangi gün','güne denk','günlerden'],
    run:function(t){
        var names=['Pazar','Pazartesi','Salı','Çarşamba','Perşembe','Cuma','Cumartesi'];
        var m=t.match(/\d{1,2}[./-]\d{1,2}[./-]\d{2,4}/);
        if(!m){
            var now=new Date();
            return {ok:true,text:'Bugün -> **'+names[now.getDay()]+'**'};
        }
        var p=m[0].split(/[./-]/),d=+p[0],mo=+p[1],y=+p[2];
        if(y<100) y+=2000;
        return {ok:true,text:m[0]+' -> **'+names[new Date(y,mo-1,d).getDay()]+'**'};
    }
},
{
    id:'tarih-ekle', name:'Tarih Ekle/Çıkar', icon:'plus',
    desc:'Bir tarihe gün ekler veya çıkarır',
    example:'01.01.2026 + 15 gün',
    keywords:['gün ekle','gün çıkar','gün sonra','gün önce'],
    run:function(t){
        var m=t.match(/(\d{1,2}[./-]\d{1,2}[./-]\d{2,4})/);
        var base=new Date();
        if(m){
            var p=m[1].split(/[./-]/);
            base=new Date(+p[2]>1000?+p[2]:2000+(+p[2]),+p[1]-1,+p[0]);
        }
        var n=t.match(/(\d+)\s*gün/);
        if(!n) return {ok:false};
        var days=+n[1]*(/çıkar|cikar|önce/.test(t)?-1:1);
        base.setDate(base.getDate()+days);
        var fmt=('0'+base.getDate()).slice(-2)+'.'+('0'+(base.getMonth()+1)).slice(-2)+'.'+base.getFullYear();
        return {ok:true,text:(m?m[1]:'bugün')+' + '+days+' gün = **'+fmt+'**'};
    }
},
{
    id:'uuid', name:'UUID Üretici', icon:'id',
    desc:'Rastgele UUID v4 üretir',
    example:'uuid üret',
    keywords:['uuid'],
    run:function(){
        function s4(){return Math.floor((1+Math.random())*0x10000).toString(16).substring(1)}
        return {ok:true,text:s4()+s4()+'-'+s4()+'-4'+s4().substring(1)+'-a'+s4().substring(1)+'-'+s4()+s4()+s4()};
    }
},
{
    id:'rastgele-isim', name:'Rastgele İsim', icon:'user',
    desc:'Rastgele Türkçe isim + soyisim üretir',
    example:'rastgele isim',
    keywords:['rastgele isim','isim üret','takma ad'],
    run:function(){
        var f=['Mert','Deniz','Elif','Zeynep','Kerem','Aylin','Emir','Selin','Baran','Derya','Cem','Leyla','Kaan','Ece','Umut','Naz'];
        var l=['Yılmaz','Kaya','Demir','Çelik','Şahin','Aydın','Öztürk','Arslan','Doğan','Kılıç','Aslan','Çetin'];
        return {ok:true,text:'**'+f[Math.floor(Math.random()*f.length)]+' '+l[Math.floor(Math.random()*l.length)]+'**'};
    }
},
{
    id:'element', name:'Element Bilgisi', icon:'alembic',
    desc:'Periyodik tablo mini — element özellikleri',
    example:'element: demir',
    keywords:['element','periyodik'],
    run:function(t){
        var map={hidrojen:['H',1],oksijen:['O',8],karbon:['C',6],azot:['N',7],demir:['Fe',26],altın:['Au',79],gümüş:['Ag',47],bakır:['Cu',29],kurşun:['Pb',82],helyum:['He',2],sodyum:['Na',11],kalsiyum:['Ca',20],altin:['Au',79],gumus:['Ag',47]};
        for(var k in map) if(t.toLowerCase().includes(k)) return {ok:true,text:'**'+k.charAt(0).toUpperCase()+k.slice(1)+'**\n\n- Sembol: **'+map[k][0]+'**\n- Atom numarası: **'+map[k][1]+'**'};
        return {ok:false};
    }
},
{
    id:'gezegen', name:'Gezegen Bilgisi', icon:'planet',
    desc:'Gezegenler hakkında bilgi verir',
    example:'mars bilgisi',
    keywords:['gezegen','bilgisi'],
    run:function(t){
        var map={merkür:'Güneş e en yakın gezegen — yüzey sıcaklığı -173°C ile 427°C arasında.',venüs:'En sıcak gezegen — yoğun CO2 atmosferi, 465°C.',dünya:'Yaşam barındırdığı bilinen tek gezegen — %71 su.',mars:'Kızıl gezegen — 2 küçük uydusu var: Phobos ve Deimos.',jüpiter:'Güneş sisteminin en büyük gezegeni — Büyük Kırmızı Leke.',satürn:'Halkalı dev — 1000 den fazla halkası var.',uranüs:'Buz devi — yan yatmış dönüyor.',neptün:'En uzak gezegen — saatte 2000 km rüzgar.'};
        for(var k in map) if(t.toLowerCase().includes(k)) return {ok:true,text:'**'+k.charAt(0).toUpperCase()+k.slice(1)+'** — '+map[k]};
        return {ok:false};
    }
},
{
    id:'pi-sayisi', name:'Pi Sayısı', icon:'π',
    desc:'Pi sayısının basamaklarını gösterir',
    example:'pi sayısı',
    keywords:['pi sayısı','3.14'],
    run:function(){
        return {ok:true,text:'**π** = 3.14159265358979323846264338327950288419716939937510\n\n(50 basamak — şu ana kadar trilyonlarca basamak hesaplandı)'};
    }
},
{
    id:'roman', name:'Roma Rakamı', icon:'Ⅰ',
    desc:'Sayıyı Roma rakamına çevirir',
    example:'1999 roman',
    keywords:['roman','roma rakamı'],
    run:function(t){
        var m=t.match(/\d{1,4}/);
        if(!m) return {ok:false};
        var n=+m[0];
        if(n<1||n>3999) return {ok:false};
        var vals=[1000,900,500,400,100,90,50,40,10,9,5,4,1],rom=['M','CM','D','CD','C','XC','L','XL','X','IX','V','IV','I'],out='';
        for(var i=0;i<vals.length;i++) while(n>=vals[i]){out+=rom[i];n-=vals[i];}
        return {ok:true,text:m[0]+' = **'+out+'**'};
    }
},
{
    id:'sayi-okunusu', name:'Sayı Okunuşu', icon:'digits',
    desc:'Sayıyı Türkçe yazıyla yazar',
    example:'12345 okunuşu',
    keywords:['okunuşu','yazıyla','kelimeyle'],
    run:function(t){
        var m=t.match(/\d{1,7}/);
        if(!m) return {ok:false};
        var n=+m[0];
        var bir=['','bir','iki','üç','dört','beş','altı','yedi','sekiz','dokuz'];
        var on=['','on','yirmi','otuz','kırk','elli','altmış','yetmiş','seksen','doksan'];
        function say(x){
            if(x===0) return '';
            var out='';
            var h=Math.floor(x/100),r=x%100;
            if(h) out+=(h===1?'yüz':bir[h]+' yüz');
            if(r){
                if(r>=10) out+=' '+on[Math.floor(r/10)];
                var o=r%10;
                if(o) out+=' '+bir[o];
            }
            return out.trim();
        }
        var words='';
        var mly=Math.floor(n/1e6),th=Math.floor((n%1e6)/1000),rest=n%1000;
        if(mly) words+=say(mly)+' milyon';
        if(th) words+=(th===1?' bin':' '+say(th)+' bin');
        if(rest) words+=' '+say(rest);
        words=words.replace(/\s+/g,' ').trim();
        return {ok:true,text:m[0]+' -> **'+words+'**'};
    }
},
{
    id:'mod-hesapla', name:'Mod Alma', icon:'divide',
    desc:'Bölme kalanını hesaplar',
    example:'17 mod 5',
    keywords:['mod','kalanı'],
    run:function(t){
        var m=t.match(/(\d+)\s*(?:mod|bölümünden kalan)\s*(\d+)/);
        if(!m) return {ok:false};
        return {ok:true,text:m[1]+' mod '+m[2]+' = **'+(+m[1]%+m[2])+'**'};
    }
},
{
    id:'dna', name:'DNA Tamamlayıcı', icon:'dna',
    desc:'DNA dizisinin tamamlayıcısını bulur',
    example:'dna: ATCG',
    keywords:['dna','gen dizisi'],
    run:function(t){
        var seq=t.replace(/^[^:(]*[:(]\s*/,'').trim().toUpperCase().match(/[ATCG]+/);
        if(!seq) return {ok:false};
        var s=seq[0],comp='';
        for(var i=s.length-1;i>=0;i--) comp+={A:'T',T:'A',C:'G',G:'C'}[s.charAt(i)];
        return {ok:true,text:'Dizi: `'+s+'`\n\nTamamlayıcı: **`'+comp+'`**'};
    }
}
];
